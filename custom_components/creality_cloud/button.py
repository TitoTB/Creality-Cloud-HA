"""Manual action buttons for Creality Cloud."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up printer buttons."""
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
            CrealityCloudPrinterButton(entry, printer_id) for printer_id in new_ids
        )

    add_printers()
    entry.async_on_unload(
        entry.runtime_data.coordinator.async_add_listener(add_printers)
    )


class CrealityCloudPrinterButton(CrealityCloudPrinterEntity, ButtonEntity):
    """Send the next configured G-code to one printer."""

    _attr_translation_key = "run_printer"
    _attr_icon = "mdi:printer-3d"

    def __init__(self, entry: CrealityCloudConfigEntry, printer_id: str) -> None:
        super().__init__(entry, printer_id, "run")

    async def async_press(self) -> None:
        """Run the next print for this profile."""
        try:
            await self.coordinator.async_run_printer(self.printer_id)
        except CrealityCloudApiError as err:
            raise HomeAssistantError(str(err)) from err
