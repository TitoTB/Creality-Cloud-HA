"""Task switches for Creality Cloud."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrealityCloudConfigEntry
from .api import CrealityCloudApiError
from .const import TASKS
from .entity import CrealityCloudEntity

TASK_ICONS = {
    "print": "mdi:printer-3d",
    "collections": "mdi:bookmark-multiple",
}


async def async_setup_entry(
    hass,
    entry: CrealityCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up task switches."""
    async_add_entities(CrealityCloudTaskSwitch(entry, task_id) for task_id in TASKS)


class CrealityCloudTaskSwitch(CrealityCloudEntity, SwitchEntity):
    """Enable or disable one CC Tools task."""

    def __init__(self, entry: CrealityCloudConfigEntry, task_id: str) -> None:
        super().__init__(entry, f"task_{task_id}")
        self.task_id = task_id
        self.entity_description = SwitchEntityDescription(
            key=task_id,
            translation_key=f"task_{task_id}",
            icon=TASK_ICONS[task_id],
        )

    @property
    def available(self) -> bool:
        """Keep collections unavailable until the add-on supports it."""
        return super().available and (
            self.task_id != "collections"
            or "collections" in self.coordinator.data.get("tasks", {})
        )

    @property
    def is_on(self) -> bool:
        """Return whether the task is enabled."""
        return (
            self.coordinator.data.get("tasks", {}).get(self.task_id, {}).get("enabled")
            is True
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the task."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the task."""
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        try:
            await self.coordinator.async_set_task_enabled(self.task_id, enabled)
        except CrealityCloudApiError as err:
            raise HomeAssistantError(str(err)) from err
