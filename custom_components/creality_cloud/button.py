"""Manual action buttons for Creality Cloud."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrealityCloudConfigEntry
from .api import CrealityCloudApiError
from .const import RUNNABLE_TASKS
from .entity import CrealityCloudEntity, CrealityCloudPrinterEntity
from .switch import TASK_ICONS


async def async_setup_entry(
    hass,
    entry: CrealityCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up manual task and printer buttons."""
    async_add_entities(
        CrealityCloudTaskButton(entry, task_id) for task_id in RUNNABLE_TASKS
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
            CrealityCloudPrinterButton(entry, printer_id) for printer_id in new_ids
        )

    add_printers()
    entry.async_on_unload(
        entry.runtime_data.coordinator.async_add_listener(add_printers)
    )


class CrealityCloudTaskButton(CrealityCloudEntity, ButtonEntity):
    """Run one CC Tools task immediately."""

    def __init__(self, entry: CrealityCloudConfigEntry, task_id: str) -> None:
        super().__init__(entry, f"run_{task_id}")
        self.task_id = task_id
        self.entity_description = ButtonEntityDescription(
            key=task_id,
            translation_key=f"run_{task_id}",
            icon=TASK_ICONS[task_id],
        )

    async def async_press(self) -> None:
        """Run the task."""
        try:
            await self.coordinator.async_run_task(self.task_id)
        except CrealityCloudApiError as err:
            raise HomeAssistantError(str(err)) from err


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
