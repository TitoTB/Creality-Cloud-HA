"""Data coordinator for Creality Cloud."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

from .api import CrealityCloudApi, CrealityCloudApiError
from .const import (
    ADDON_SLUG,
    AUTO_RESTART_COOLDOWN,
    AUTO_RESTART_LIMIT,
    AUTO_RESTART_STABILIZATION,
    AUTO_RESTART_WINDOW,
    CONF_AUTO_RESTART,
    DOMAIN,
    EVENT_PREFIX,
    MISSED_SLOT_GRACE,
    SCAN_INTERVAL,
    STALE_RESTART_DELAY,
)
from .watchdog import (
    missed_schedule_slots,
    monitoring_block_reason,
    parse_datetime,
    recent_restarts,
    stale_signature,
    stale_started_at,
)

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
        self.entry = entry
        self._known_event_ids: set[str] | None = None
        self._watchdog_store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.watchdog"
        )
        self._watchdog_loaded = False
        self._restart_timestamps: list[datetime] = []
        self._last_restart_at: datetime | None = None
        self._last_restart_reason = ""
        self._stabilizing_until: datetime | None = None
        self._stale_signature: tuple[str, str, str] | None = None
        self._stale_since: datetime | None = None
        self._restart_in_progress = False
        self._watchdog_status = "disabled"

    async def _async_update_data(self) -> dict[str, Any]:
        await self._async_load_watchdog_state()
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
        await self._async_consider_auto_restart(state)
        return state

    @property
    def auto_restart_enabled(self) -> bool:
        """Return whether automatic recovery is enabled."""
        return self.entry.options.get(CONF_AUTO_RESTART, False) is True

    @property
    def watchdog_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes for the automatic restart switch."""
        now = datetime.now(UTC)
        restarts = recent_restarts(
            self._restart_timestamps, now, AUTO_RESTART_WINDOW
        )
        return {
            "status": self._watchdog_status,
            "last_restart_at": (
                self._last_restart_at.isoformat() if self._last_restart_at else None
            ),
            "last_restart_reason": self._last_restart_reason or None,
            "restarts_last_24h": len(restarts),
        }

    async def async_set_auto_restart_enabled(self, enabled: bool) -> None:
        """Enable or disable automatic recovery locally in Home Assistant."""
        options = {**self.entry.options, CONF_AUTO_RESTART: enabled}
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        if not enabled:
            self._reset_stale_tracking()
            self._watchdog_status = "disabled"
        else:
            self._watchdog_status = "monitoring"
        self.async_update_listeners()

    async def _async_load_watchdog_state(self) -> None:
        if self._watchdog_loaded:
            return
        stored = await self._watchdog_store.async_load() or {}
        self._restart_timestamps = recent_restarts(
            list(stored.get("restart_timestamps") or []),
            datetime.now(UTC),
            AUTO_RESTART_WINDOW,
        )
        self._last_restart_at = parse_datetime(stored.get("last_restart_at"))
        self._last_restart_reason = str(stored.get("last_restart_reason") or "")
        self._watchdog_loaded = True

    async def _async_consider_auto_restart(self, state: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        if not self.auto_restart_enabled:
            self._reset_stale_tracking()
            self._watchdog_status = "disabled"
            return

        blocked = monitoring_block_reason(state, now)
        if blocked:
            self._reset_stale_tracking()
            self._watchdog_status = blocked
            return
        if self._stabilizing_until and now < self._stabilizing_until:
            self._reset_stale_tracking()
            self._watchdog_status = "stabilizing"
            return

        signature = stale_signature(state)
        if signature is None:
            self._reset_stale_tracking()
        elif signature != self._stale_signature:
            self._stale_signature = signature
            self._stale_since = stale_started_at(state, now)

        reason = ""
        if (
            signature is not None
            and self._stale_since is not None
            and now - self._stale_since >= STALE_RESTART_DELAY
        ):
            reason = "scheduler_stale_30m"
        elif signature is None:
            missed = missed_schedule_slots(state, now, MISSED_SLOT_GRACE)
            if len(missed) >= 2:
                first, second = missed[0], missed[1]
                reason = (
                    "two_missed_slots:"
                    f"{first.get('task', 'unknown')}@{first.get('plannedAt', '')},"
                    f"{second.get('task', 'unknown')}@{second.get('plannedAt', '')}"
                )

        if not reason:
            self._watchdog_status = "monitoring"
            return
        await self._async_restart_if_allowed(reason, now)

    async def _async_restart_if_allowed(self, reason: str, now: datetime) -> None:
        if self._restart_in_progress:
            self._watchdog_status = "restart_in_progress"
            return
        if self._stabilizing_until and now < self._stabilizing_until:
            self._watchdog_status = "stabilizing"
            return

        self._restart_timestamps = recent_restarts(
            self._restart_timestamps, now, AUTO_RESTART_WINDOW
        )
        if (
            self._restart_timestamps
            and now - self._restart_timestamps[-1] < AUTO_RESTART_COOLDOWN
        ):
            self._watchdog_status = "cooldown"
            return
        if len(self._restart_timestamps) >= AUTO_RESTART_LIMIT:
            self._watchdog_status = "daily_limit"
            return
        if not self.hass.services.has_service("hassio", "app_restart"):
            self._watchdog_status = "restart_service_unavailable"
            _LOGGER.warning(
                "CC Tools appears stalled, but hassio.app_restart is unavailable"
            )
            return

        self._restart_in_progress = True
        self._watchdog_status = "restart_in_progress"
        try:
            _LOGGER.warning("Restarting CC Tools automatically: %s", reason)
            await self.hass.services.async_call(
                "hassio",
                "app_restart",
                {"app": ADDON_SLUG},
                blocking=True,
            )
        except Exception:  # Home Assistant reports service failures through exceptions.
            self._watchdog_status = "restart_failed"
            _LOGGER.exception("Could not restart CC Tools automatically")
            return
        finally:
            self._restart_in_progress = False

        self._restart_timestamps.append(now)
        self._last_restart_at = now
        self._last_restart_reason = reason
        self._stabilizing_until = now + AUTO_RESTART_STABILIZATION
        self._watchdog_status = "stabilizing"
        self._reset_stale_tracking()
        await self._watchdog_store.async_save(
            {
                "restart_timestamps": [
                    value.isoformat() for value in self._restart_timestamps
                ],
                "last_restart_at": now.isoformat(),
                "last_restart_reason": reason,
            }
        )

    def _reset_stale_tracking(self) -> None:
        self._stale_signature = None
        self._stale_since = None

    async def async_run_task(self, task_id: str) -> None:
        """Run a task and refresh all entities."""
        await self.api.async_run_task(task_id)
        await self.async_request_refresh()

    async def async_set_task_enabled(self, task_id: str, enabled: bool) -> None:
        """Set task state and refresh all entities."""
        await self.api.async_set_task_enabled(task_id, enabled)
        await self.async_request_refresh()
