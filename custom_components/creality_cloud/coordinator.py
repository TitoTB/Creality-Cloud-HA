"""Data coordinator for Creality Cloud."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CrealityCloudApi, CrealityCloudApiError
from .const import DOMAIN, EVENT_PREFIX, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class CrealityCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll CC Tools and publish newly completed events."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: CrealityCloudApi,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self.api = api
        self._known_event_ids: set[str] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            state = await self.api.async_status()
            events = await self.api.async_events()
        except CrealityCloudApiError as err:
            raise UpdateFailed(str(err)) from err

        event_ids = {str(event.get("id") or "") for event in events if event.get("id")}
        if self._known_event_ids is not None:
            for event in reversed(events):
                event_id = str(event.get("id") or "")
                if event_id and event_id not in self._known_event_ids:
                    event_type = str(event.get("type") or "").strip()
                    if event_type:
                        self.hass.bus.async_fire(f"{EVENT_PREFIX}_{event_type}", event)
        self._known_event_ids = event_ids
        return state

    async def async_run_task(self, task_id: str) -> None:
        """Run a task and refresh all entities."""
        await self.api.async_run_task(task_id)
        await self.async_request_refresh()

    async def async_set_task_enabled(self, task_id: str, enabled: bool) -> None:
        """Set task state and refresh all entities."""
        await self.api.async_set_task_enabled(task_id, enabled)
        await self.async_request_refresh()
