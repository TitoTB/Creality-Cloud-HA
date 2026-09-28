"""Task switches for Creality Cloud."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrealityCloudConfigEntry
from .api import CrealityCloudApiError
from .entity import CrealityCloudPrinterEntity


async def async_setup_entry(
    hass,
    entry: CrealityCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scheduled-print switches for discovered printers."""
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
            CrealityCloudPrinterScheduleSwitch(entry, printer_id)
            for printer_id in new_ids
        )

    add_printers()
    entry.async_on_unload(
        entry.runtime_data.coordinator.async_add_listener(add_printers)
    )


class CrealityCloudPrinterScheduleSwitch(CrealityCloudPrinterEntity, SwitchEntity):
    """Enable or disable scheduled prints from a printer device."""

    def __init__(self, entry: CrealityCloudConfigEntry, printer_id: str) -> None:
        super().__init__(entry, printer_id, "scheduled_prints")
        self.entity_description = SwitchEntityDescription(
            key="scheduled_prints",
            translation_key="printer_scheduled_prints",
            icon="mdi:printer-3d",
        )

    @property
    def is_on(self) -> bool:
        """Return whether the task is enabled."""
        return self.printer.get("enabled") is True

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the task."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the task."""
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        try:
            await self.coordinator.async_set_task_enabled("print", enabled)
        except CrealityCloudApiError as err:
            raise HomeAssistantError(str(err)) from err
