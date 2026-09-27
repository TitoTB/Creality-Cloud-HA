"""Config flow for Creality Cloud."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CrealityCloudApi, CrealityCloudApiError
from .const import CONF_URL, DEFAULT_ADDON_URLS, DOMAIN


async def async_probe_url(hass: HomeAssistant, url: str) -> dict[str, Any]:
    """Validate one CC Tools endpoint."""
    return await CrealityCloudApi(
        async_get_clientsession(hass), url, request_timeout=5
    ).async_status()


class CrealityCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Creality Cloud config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._url = ""
        self._state: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Try the add-on automatically, then fall back to a URL form."""
        if user_input is not None:
            return await self._async_validate_url(str(user_input[CONF_URL]))

        detected = await self._async_detect_addon()
        if detected:
            self._url, self._state = detected
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_URL): str}),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm an automatically detected add-on."""
        if user_input is not None:
            return await self._async_create_entry()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"url": self._url},
        )

    async def _async_detect_addon(self) -> tuple[str, dict[str, Any]] | None:
        tasks = [
            asyncio.create_task(self._probe(candidate))
            for candidate in DEFAULT_ADDON_URLS
        ]
        try:
            for completed in asyncio.as_completed(tasks):
                if result := await completed:
                    return result
            return None
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _probe(self, url: str) -> tuple[str, dict[str, Any]] | None:
        try:
            return url, await async_probe_url(self.hass, url)
        except CrealityCloudApiError:
            return None

    async def _async_validate_url(self, value: str) -> ConfigFlowResult:
        url = normalize_url(value)
        if not url:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_URL, default=value): str}),
                errors={CONF_URL: "invalid_url"},
            )
        try:
            state = await async_probe_url(self.hass, url)
        except CrealityCloudApiError:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_URL, default=url): str}),
                errors={"base": "cannot_connect"},
            )
        self._url = url
        self._state = state
        return await self._async_create_entry()

    async def _async_create_entry(self) -> ConfigFlowResult:
        account = self._state.get("account", {})
        unique_id = str(account.get("userId") or self._url)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_URL: self._url})
        return self.async_create_entry(
            title=str(account.get("name") or "Creality Cloud"),
            data={CONF_URL: self._url},
        )


def normalize_url(value: str) -> str:
    """Return a normalized HTTP URL or an empty string."""
    raw = str(value or "").strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return raw
