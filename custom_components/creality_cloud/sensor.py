"""Sensors exposed by Creality Cloud."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrealityCloudConfigEntry
from .const import TASKS
from .entity import CrealityCloudEntity, CrealityCloudPrinterEntity


@dataclass(frozen=True, kw_only=True)
class CrealityCloudSensorDescription(SensorEntityDescription):
    """Describe a value in the coordinator payload."""

    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


ACCOUNT_SENSORS = (
    CrealityCloudSensorDescription(
        key="points_total",
        translation_key="points_total",
        icon="mdi:star-circle",
        native_unit_of_measurement="points",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("points", {}).get("total"),
    ),
    CrealityCloudSensorDescription(
        key="points_today",
        translation_key="points_today",
        icon="mdi:star-plus",
        native_unit_of_measurement="points",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("points", {}).get("earnedToday"),
    ),
    CrealityCloudSensorDescription(
        key="lottery_tickets",
        translation_key="lottery_tickets",
        icon="mdi:ticket-confirmation",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("rewards", {}).get("lotteryTickets"),
    ),
    CrealityCloudSensorDescription(
        key="boosts_available",
        translation_key="boosts_available",
        icon="mdi:rocket-launch",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("rewards", {}).get("boostsAvailable"),
    ),
    CrealityCloudSensorDescription(
        key="latest_order",
        translation_key="latest_order",
        icon="mdi:package-variant-closed",
        value_fn=lambda data: (
            data.get("orders", {}).get("latest") or {}
        ).get("status"),
        attributes_fn=lambda data: latest_order_attributes(data),
    ),
)

TASK_SENSORS = tuple(
    description
    for task_id in TASKS
    for description in (
        CrealityCloudSensorDescription(
            key=f"{task_id}_daily_count",
            translation_key=f"{task_id}_daily_count",
            icon="mdi:counter",
            state_class=SensorStateClass.TOTAL,
            value_fn=lambda data, current=task_id: (
                data.get("tasks", {}).get(current, {}).get("dailyCount")
            ),
            attributes_fn=lambda data, current=task_id: {
                "daily_limit": data.get("tasks", {}).get(current, {}).get("dailyLimit"),
                "last_status": data.get("tasks", {}).get(current, {}).get("lastStatus"),
                "last_message": data.get("tasks", {})
                .get(current, {})
                .get("lastMessage"),
            },
        ),
        CrealityCloudSensorDescription(
            key=f"{task_id}_last_run",
            translation_key=f"{task_id}_last_run",
            icon="mdi:history",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=lambda data, current=task_id: parse_datetime(
                data.get("tasks", {}).get(current, {}).get("lastRunAt")
            ),
        ),
        CrealityCloudSensorDescription(
            key=f"{task_id}_next_run",
            translation_key=f"{task_id}_next_run",
            icon="mdi:clock-outline",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=lambda data, current=task_id: parse_datetime(
                data.get("tasks", {}).get(current, {}).get("nextRunAt")
            ),
        ),
    )
)

PRINTER_SENSOR_KEYS = ("status", "daily_count", "last_run", "next_run", "last_gcode")


async def async_setup_entry(
    hass,
    entry: CrealityCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up account and dynamically discovered printer sensors."""
    async_add_entities(
        CrealityCloudSensor(entry, description) for description in (*ACCOUNT_SENSORS, *TASK_SENSORS)
    )
    known_printers: set[str] = set()

    @callback
    def add_printers() -> None:
        new_ids = {
            str(printer.get("id"))
            for printer in entry.runtime_data.coordinator.data.get("printers", [])
            if printer.get("id") and printer.get("id") not in known_printers
        }
        if not new_ids:
            return
        known_printers.update(new_ids)
        async_add_entities(
            CrealityCloudPrinterSensor(entry, printer_id, key)
            for printer_id in new_ids
            for key in PRINTER_SENSOR_KEYS
        )

    add_printers()
    entry.async_on_unload(
        entry.runtime_data.coordinator.async_add_listener(add_printers)
    )


class CrealityCloudSensor(CrealityCloudEntity, SensorEntity):
    """Generic account sensor."""

    entity_description: CrealityCloudSensorDescription

    def __init__(self, entry, description: CrealityCloudSensorDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Do not report collection values when the add-on lacks support."""
        return super().available and (
            not self.entity_description.key.startswith("collections_")
            or "collections" in self.coordinator.data.get("tasks", {})
        )

    @property
    def native_value(self):
        """Return the latest value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        """Return useful diagnostics without exposing private configuration."""
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.coordinator.data)
        return None


class CrealityCloudPrinterSensor(CrealityCloudPrinterEntity, SensorEntity):
    """Sensor associated with a printer profile."""

    def __init__(self, entry, printer_id: str, key: str) -> None:
        super().__init__(entry, printer_id, key)
        self.key = key
        self._attr_translation_key = f"printer_{key}"
        if key in {"last_run", "next_run"}:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        if key == "status":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["ready", "disabled", "unavailable"]
        self._attr_icon = {
            "status": "mdi:printer-3d",
            "daily_count": "mdi:counter",
            "last_run": "mdi:history",
            "next_run": "mdi:clock-outline",
            "last_gcode": "mdi:file-code",
        }[key]

    @property
    def native_value(self):
        """Return the current printer value."""
        if self.key == "status":
            if not self.printer.get("enabled"):
                return "disabled"
            return "ready" if self.printer.get("available") else "unavailable"
        if self.key == "daily_count":
            return self.printer.get("dailyCount")
        if self.key == "last_run":
            return parse_datetime(self.printer.get("lastRunAt"))
        if self.key == "next_run":
            return parse_datetime(self.printer.get("nextRunAt"))
        return self.printer.get("lastGcode") or None

    @property
    def extra_state_attributes(self):
        """Expose the daily print limit and last result."""
        if self.key == "daily_count":
            return {"daily_limit": self.printer.get("dailyLimit")}
        if self.key == "status":
            return {"last_status": self.printer.get("lastStatus")}
        return None


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp for a timestamp sensor."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def latest_order_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """Return useful details about the most recently created shop order."""
    order = data.get("orders", {}).get("latest")
    if not isinstance(order, dict):
        return {}
    return {
        "order_id": order.get("id"),
        "order_number": order.get("orderNumber"),
        "product": order.get("title"),
        "points": order.get("points"),
        "quantity": order.get("quantity"),
        "region": order.get("region"),
        "status_kind": order.get("statusKind"),
        "created_at": order.get("createdAt"),
        "updated_at": order.get("updatedAt"),
        "image_url": order.get("imageUrl"),
    }
