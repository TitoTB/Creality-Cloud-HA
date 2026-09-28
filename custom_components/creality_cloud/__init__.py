"""Creality Cloud integration backed by the CC Tools add-on."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CrealityCloudApi
from .const import CONF_URL, DOMAIN, PLATFORMS, REMOVED_ENTITY_UNIQUE_ID_SUFFIXES
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

    entity_registry = er.async_get(hass)
    for suffix in REMOVED_ENTITY_UNIQUE_ID_SUFFIXES:
        unique_id = f"{entry.entry_id}_{suffix}"
        for platform in ("button", "sensor", "switch"):
            entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
            if entity_id:
                entity_registry.async_remove(entity_id)

    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if (
            registry_entry.platform == DOMAIN
            and registry_entry.entity_id.startswith("button.")
            and registry_entry.unique_id != f"{entry.entry_id}_run_collections"
        ):
            entity_registry.async_remove(registry_entry.entity_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CrealityCloudConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
