"""Constants for the Creality Cloud integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "creality_cloud"
PLATFORMS = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
SCAN_INTERVAL = timedelta(seconds=30)

CONF_URL = "url"
DEFAULT_ADDON_URLS = (
    "http://8966b8c7-cc-tools:8080",
    "http://cc-tools:8080",
    "http://homeassistant.local:8080",
)

EVENT_PREFIX = "creality_cloud"

TASKS = ("collections",)

REMOVED_ENTITY_UNIQUE_ID_SUFFIXES = (
    "automation_status",
    "browser_status",
    "scheduler_status",
    "orders_pending",
    "orders_shipped",
    "print_daily_count",
    "print_last_run",
    "print_next_run",
    "task_print",
    *(
        f"{task_id}_{suffix}"
        for task_id in ("checkin", "downloads", "comments", "boosts", "likes")
        for suffix in ("daily_count", "last_run", "next_run")
    ),
    *(
        f"task_{task_id}"
        for task_id in ("checkin", "downloads", "comments", "boosts", "likes")
    ),
    *(
        f"run_{task_id}"
        for task_id in ("checkin", "downloads", "comments", "boosts", "likes")
    ),
)
