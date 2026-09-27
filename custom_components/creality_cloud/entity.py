"""Entity helpers for Creality Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CrealityCloudConfigEntry
from .const import DOMAIN
from .coordinator import CrealityCloudCoordinator


class CrealityCloudEntity(CoordinatorEntity[CrealityCloudCoordinator]):
    """Base entity attached to the Creality Cloud account device."""

    _attr_has_entity_name = True

    def __init__(self, entry: CrealityCloudConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data.coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the account device."""
        account = self.coordinator.data.get("account", {})
        return DeviceInfo(
            identifiers={(DOMAIN, f"account:{self.entry.entry_id}")},
            manufacturer="Creality Cloud",
            model="CC Tools account",
            name=str(account.get("name") or self.entry.title or "Creality Cloud"),
            configuration_url=self.entry.data.get("url"),
        )


class CrealityCloudPrinterEntity(CrealityCloudEntity):
    """Base entity attached to one configured printer."""

    def __init__(
        self,
        entry: CrealityCloudConfigEntry,
        printer_id: str,
        key: str,
    ) -> None:
        super().__init__(entry, f"printer_{printer_id}_{key}")
        self.printer_id = printer_id

    @property
    def printer(self) -> dict[str, Any]:
        """Return the latest printer payload."""
        return next(
            (
                printer
                for printer in self.coordinator.data.get("printers", [])
                if printer.get("id") == self.printer_id
            ),
            {},
        )

    @property
    def available(self) -> bool:
        """Keep the printer entity available while its profile exists."""
        return super().available and bool(self.printer)

    @property
    def device_info(self) -> DeviceInfo:
        """Return printer device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}:printer:{self.printer_id}")},
            manufacturer="Creality",
            model="Creality Cloud printer",
            name=str(self.printer.get("name") or self.printer_id),
            via_device=(DOMAIN, f"account:{self.entry.entry_id}"),
            configuration_url=self.entry.data.get("url"),
        )
