"""Pure watchdog rules for detecting a stalled CC Tools scheduler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp and normalize it to UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def monitoring_block_reason(data: dict[str, Any], now: datetime) -> str | None:
    """Return why watchdog evaluation must be suspended."""
    health = data.get("health") or {}
    paused_until = parse_datetime(health.get("pausedUntil"))
    if str(health.get("state") or "").lower() == "paused":
        return "paused"
    if paused_until and paused_until > now:
        return "paused"

    scheduler = data.get("scheduler") or {}
    if str(scheduler.get("browserMode") or "").lower() == "interactive":
        return "interactive_browser"
    return None


def latest_execution_at(data: dict[str, Any]) -> datetime | None:
    """Return the newest execution reported by any task or printer."""
    timestamps: list[datetime] = []
    for task in (data.get("tasks") or {}).values():
        parsed = parse_datetime((task or {}).get("lastRunAt"))
        if parsed:
            timestamps.append(parsed)
    for printer in data.get("printers") or []:
        parsed = parse_datetime((printer or {}).get("lastRunAt"))
        if parsed:
            timestamps.append(parsed)
    return max(timestamps, default=None)


def missed_schedule_slots(
    data: dict[str, Any],
    now: datetime,
    grace: timedelta,
) -> list[dict[str, Any]]:
    """Return overdue consecutive slots not followed by another execution."""
    if monitoring_block_reason(data, now):
        return []

    scheduler = data.get("scheduler") or {}
    if scheduler.get("running") is True:
        return []

    latest_execution = latest_execution_at(data)
    deadline = now - grace
    missed: list[tuple[datetime, dict[str, Any]]] = []
    for slot in (data.get("schedule") or {}).get("pending") or []:
        planned_at = parse_datetime((slot or {}).get("plannedAt"))
        if not planned_at or planned_at > deadline:
            continue
        if latest_execution and latest_execution > planned_at:
            continue
        missed.append((planned_at, slot))

    missed.sort(key=lambda item: item[0])
    return [slot for _, slot in missed]


def stale_signature(data: dict[str, Any]) -> tuple[str, str, str] | None:
    """Return a stable identity for the currently stale operation."""
    scheduler = data.get("scheduler") or {}
    if scheduler.get("running") is not True or scheduler.get("stale") is not True:
        return None
    return (
        str(scheduler.get("runningTask") or ""),
        str(scheduler.get("startedAt") or ""),
        str(scheduler.get("timeoutAt") or ""),
    )


def stale_started_at(data: dict[str, Any], observed_at: datetime) -> datetime:
    """Anchor stale duration to the operation timeout when it is trustworthy."""
    timeout_at = parse_datetime((data.get("scheduler") or {}).get("timeoutAt"))
    if timeout_at and timeout_at <= observed_at:
        return timeout_at
    return observed_at


def recent_restarts(
    values: list[Any], now: datetime, window: timedelta
) -> list[datetime]:
    """Return valid restart timestamps inside the protection window."""
    minimum = now - window
    return sorted(
        parsed
        for value in values
        if (parsed := parse_datetime(value)) is not None and parsed >= minimum
    )
