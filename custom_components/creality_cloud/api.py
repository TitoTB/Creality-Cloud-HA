"""HTTP client for the CC Tools Home Assistant API."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientError, ClientSession, ClientTimeout


class CrealityCloudApiError(Exception):
    """Base API error."""


class CrealityCloudConnectionError(CrealityCloudApiError):
    """Raised when CC Tools cannot be reached."""


class CrealityCloudResponseError(CrealityCloudApiError):
    """Raised when CC Tools rejects a request."""

    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.code = code


class CrealityCloudApi:
    """Small async client for the versioned integration endpoints."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        request_timeout: float = 20,
    ) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")
        self._request_timeout = request_timeout

    async def async_status(self) -> dict[str, Any]:
        """Return the current CC Tools state."""
        return await self._request("GET", "/api/integration/status")

    async def async_events(self) -> list[dict[str, Any]]:
        """Return recent events."""
        payload = await self._request("GET", "/api/integration/events?limit=100")
        return list(payload.get("events") or [])

    async def async_set_task_enabled(self, task_id: str, enabled: bool) -> None:
        """Enable or disable a task."""
        await self._request(
            "PATCH",
            f"/api/integration/tasks/{task_id}",
            json={"enabled": enabled},
        )

    async def async_run_task(self, task_id: str) -> None:
        """Run a task immediately."""
        await self._request("POST", f"/api/integration/tasks/{task_id}/run")

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                urljoin(f"{self.base_url}/", path.lstrip("/")),
                timeout=ClientTimeout(total=self._request_timeout),
                **kwargs,
            ) as response:
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise CrealityCloudConnectionError(str(err)) from err

        if response.status >= 400 or payload.get("ok") is not True:
            code = str(payload.get("error") or "")
            message = str(payload.get("message") or code or f"HTTP {response.status}")
            raise CrealityCloudResponseError(message, code) from None
        if int(payload.get("apiVersion", 1)) != 1:
            raise CrealityCloudResponseError(
                "Unsupported CC Tools API version", "API_VERSION_UNSUPPORTED"
            )
        return payload
