"""Isolated entity logic tests; Home Assistant base classes are test doubles.

Run with python -m unittest discover -s tests -v. Hassfest validates HA metadata.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "creality_cloud"


class BaseEntity:
    def __init__(self, entry, key):
        self.coordinator = entry.runtime_data.coordinator
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def available(self):
        return self.coordinator.last_update_success


class ApiError(Exception):
    pass


class HAError(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class Description:
    key: str
    translation_key: str = ""
    icon: str = ""
    native_unit_of_measurement: str | None = None
    state_class: str | None = None
    device_class: str | None = None


def load_logic(filename, names, **extra):
    """Execute production definitions without importing the HA runtime."""
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if (
        getattr(node, "name", None) in names
        or isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)
    )]
    env = {
        "__name__": __name__, "CrealityCloudEntity": BaseEntity,
        "ButtonEntity": type("ButtonEntity", (), {}),
        "SwitchEntity": type("SwitchEntity", (), {}),
        "SensorEntity": type("SensorEntity", (), {}),
        "SwitchEntityDescription": Description, "SensorEntityDescription": Description,
        "CrealityCloudApiError": ApiError, "HomeAssistantError": HAError,
        "SensorDeviceClass": SimpleNamespace(TIMESTAMP="timestamp"),
        "SensorStateClass": SimpleNamespace(TOTAL="total"),
        "dataclass": dataclass, "datetime": datetime,
        **extra,
    }
    exec(compile(tree, filename, "exec"), env)
    return env


TASKS = load_logic("const.py", {"TASKS"})["TASKS"]
BUTTON = load_logic("button.py", {"CrealityCloudCollectionButton"})["CrealityCloudCollectionButton"]
SWITCH = load_logic("switch.py", {"TASK_ICONS", "CrealityCloudTaskSwitch"})["CrealityCloudTaskSwitch"]
SENSORS = load_logic("sensor.py", {
    "CrealityCloudSensorDescription", "TASK_SENSORS", "ACCOUNT_SENSORS",
    "CrealityCloudSensor", "parse_datetime", "latest_order_attributes"
}, TASKS=TASKS)


class CollectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.coordinator = SimpleNamespace(
            last_update_success=True,
            data={"tasks": {"collections": {
                "enabled": False, "dailyCount": 1, "dailyLimit": 1,
                "lastStatus": "success", "lastMessage": "Punto acreditado",
                "lastRunAt": "2026-09-28T08:00:00Z", "nextRunAt": "",
            }}},
            async_run_task=AsyncMock(), async_set_task_enabled=AsyncMock(),
        )
        self.entry = SimpleNamespace(entry_id="account", runtime_data=SimpleNamespace(coordinator=self.coordinator))

    async def test_manual_run_uses_collections_even_when_scheduling_disabled(self):
        button = BUTTON(self.entry)
        self.assertTrue(button.available)
        self.assertEqual(button._attr_unique_id, "account_run_collections")
        await button.async_press()
        self.coordinator.async_run_task.assert_awaited_once_with("collections")

    async def test_api_routes_collection_controls_to_companion_endpoints(self):
        api_class = load_logic("api.py", {"CrealityCloudApi"})["CrealityCloudApi"]
        api = api_class(None, "http://cc-tools:8080")
        api._request = AsyncMock()
        await api.async_run_task("collections")
        await api.async_set_task_enabled("collections", True)
        calls = api._request.await_args_list
        self.assertEqual(calls[0].args, ("POST", "/api/integration/tasks/collections/run"))
        self.assertEqual(calls[1].args, ("PATCH", "/api/integration/tasks/collections"))
        self.assertEqual(calls[1].kwargs, {"json": {"enabled": True}})

    async def test_switch_updates_scheduling_and_reads_backend_state(self):
        switch = SWITCH(self.entry, "collections")
        self.assertFalse(switch.is_on)
        await switch.async_turn_on()
        await switch.async_turn_off()
        self.assertEqual([call.args for call in self.coordinator.async_set_task_enabled.await_args_list],
                         [("collections", True), ("collections", False)])
        self.coordinator.data["tasks"]["collections"]["enabled"] = True
        self.assertTrue(switch.is_on)

    async def test_backend_rejections_become_home_assistant_errors(self):
        self.coordinator.async_run_task.side_effect = ApiError("Ya hay una ejecución")
        self.coordinator.async_set_task_enabled.side_effect = ApiError("Activa Descubrir diseños")
        with self.assertRaisesRegex(HAError, "Ya hay una ejecución"):
            await BUTTON(self.entry).async_press()
        with self.assertRaisesRegex(HAError, "Activa Descubrir diseños"):
            await SWITCH(self.entry, "collections").async_turn_on()

    def collection_sensors(self):
        return {description.key: SENSORS["CrealityCloudSensor"](self.entry, description)
                for description in SENSORS["TASK_SENSORS"] if description.key.startswith("collections_")}

    def test_sensors_use_verified_count_and_timezone_aware_dates(self):
        sensors = self.collection_sensors()
        self.assertEqual(len(sensors), 3)
        count = sensors["collections_daily_count"]
        self.assertEqual(count.native_value, 1)
        self.assertEqual(count.extra_state_attributes["daily_limit"], 1)
        self.assertEqual(count.extra_state_attributes["last_status"], "success")
        self.assertIsNotNone(sensors["collections_last_run"].native_value.tzinfo)
        self.assertIsNone(sensors["collections_next_run"].native_value)

    def test_capabilities_and_connection_control_availability(self):
        entities = [BUTTON(self.entry), SWITCH(self.entry, "collections"), *self.collection_sensors().values()]
        self.coordinator.data["tasks"] = {"print": {}}
        self.assertTrue(all(not entity.available for entity in entities))
        self.coordinator.data["tasks"]["collections"] = {}
        self.assertTrue(all(entity.available for entity in entities))
        self.coordinator.last_update_success = False
        self.assertTrue(all(not entity.available for entity in entities))

    def test_only_collection_entities_added_and_translations_complete(self):
        self.assertEqual(TASKS, ("collections",))
        for filename in ("strings.json", "translations/en.json", "translations/es.json"):
            entities = json.loads((ROOT / filename).read_text(encoding="utf-8"))["entity"]
            for platform, keys in {"button": ["run_collections"], "switch": ["task_collections"],
                                   "sensor": list(self.collection_sensors())}.items():
                for key in keys:
                    self.assertTrue(entities[platform][key]["name"])

    def test_latest_order_from_main_is_preserved(self):
        description = next(item for item in SENSORS["ACCOUNT_SENSORS"] if item.key == "latest_order")
        data = {"orders": {"latest": {"id": "order-1", "status": "Shipped", "title": "Filament"}}}
        self.assertEqual(description.value_fn(data), "Shipped")
        self.assertEqual(description.attributes_fn(data)["order_id"], "order-1")

    async def test_setup_keeps_collection_button_and_removes_old_printer_button(self):
        removed = []
        entries = [
            SimpleNamespace(platform="creality_cloud", entity_id="button.custom_collection",
                            unique_id="account_run_collections"),
            SimpleNamespace(platform="creality_cloud", entity_id="button.printer",
                            unique_id="account_printer_1_run"),
            SimpleNamespace(platform="creality_cloud", entity_id="switch.printer",
                            unique_id="account_printer_1_scheduled_prints"),
        ]
        registry = SimpleNamespace(async_remove=removed.append)
        coordinator = SimpleNamespace(data={"account": {"name": "Test"}},
                                      async_config_entry_first_refresh=AsyncMock())
        hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()))
        entry = SimpleNamespace(entry_id="account", title="Test", data={"url": "http://cc-tools"})
        env = load_logic("__init__.py", {"async_setup_entry"},
                         CrealityCloudApi=lambda *args: None,
                         CrealityCloudCoordinator=lambda *args: coordinator,
                         CrealityCloudRuntimeData=lambda api, coordinator: SimpleNamespace(api=api, coordinator=coordinator),
                         CONF_URL="url", DOMAIN="creality_cloud", PLATFORMS=["button", "sensor", "switch"],
                         REMOVED_ENTITY_UNIQUE_ID_SUFFIXES=(),
                         async_get_clientsession=lambda hass: None,
                         er=SimpleNamespace(async_get=lambda hass: registry,
                                            async_entries_for_config_entry=lambda *args: entries))
        await env["async_setup_entry"](hass, entry)
        self.assertEqual(removed, ["button.printer"])


if __name__ == "__main__":
    unittest.main()
