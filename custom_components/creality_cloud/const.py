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

TASKS = ("checkin", "print", "downloads", "comments", "boosts", "likes")
RUNNABLE_TASKS = ("checkin", "downloads", "comments", "boosts", "likes")
