"""Manual collection action for Creality Cloud."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CrealityCloudConfigEntry
from .api import CrealityCloudApiError
from .entity import CrealityCloudEntity


async def async_setup_entry(
    hass,
    entry: CrealityCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the collection action on the account device."""
    async_add_entities([CrealityCloudCollectionButton(entry)])


class CrealityCloudCollectionButton(CrealityCloudEntity, ButtonEntity):
    """Add a model to the collection through CC Tools."""

    _attr_translation_key = "run_collections"
    _attr_icon = "mdi:bookmark-plus"

    def __init__(self, entry: CrealityCloudConfigEntry) -> None:
        super().__init__(entry, "run_collections")

    @property
    def available(self) -> bool:
        """Require collection support in the connected add-on."""
        return super().available and "collections" in self.coordinator.data.get("tasks", {})

    async def async_press(self) -> None:
        """Request one collection run; CC Tools verifies the reward."""
        try:
            await self.coordinator.async_run_task("collections")
        except CrealityCloudApiError as err:
            raise HomeAssistantError(str(err)) from err
