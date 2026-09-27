"""Creality Cloud integration backed by the CC Tools add-on."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CrealityCloudApi
from .const import CONF_URL, PLATFORMS
from .coordinator import CrealityCloudCoordinator


@dataclass
class CrealityCloudRuntimeData:
    """Runtime objects associated with a config entry."""

    api: CrealityCloudApi
    coordinator: CrealityCloudCoordinator


type CrealityCloudConfigEntry = ConfigEntry[CrealityCloudRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: CrealityCloudConfigEntry
) -> bool:
    """Set up Creality Cloud from a config entry."""
    api = CrealityCloudApi(async_get_clientsession(hass), entry.data[CONF_URL])
    coordinator = CrealityCloudCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = CrealityCloudRuntimeData(api, coordinator)

    account_name = str(
        coordinator.data.get("account", {}).get("name") or "Creality Cloud"
    )
    if entry.title != account_name:
        hass.config_entries.async_update_entry(entry, title=account_name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CrealityCloudConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
