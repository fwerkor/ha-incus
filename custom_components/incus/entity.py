"""Common entity identities for Incus hosts and instances."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IncusCoordinator, InstanceKey
from .model import InstanceData


class IncusInstanceEntity(CoordinatorEntity[IncusCoordinator]):
    """Entity representing one container or virtual machine."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IncusCoordinator,
        entry: ConfigEntry,
        key: InstanceKey,
    ) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{key[0]}/{key[1]}")},
            name=f"{key[1]} ({key[0]})",
            manufacturer="Linux Containers",
            model="Incus virtual machine"
            if coordinator.data[key].kind == "virtual-machine"
            else "Incus container",
            via_device=(DOMAIN, f"{entry.entry_id}:host"),
        )

    @property
    def instance(self) -> InstanceData | None:
        """The current data, or None for an instance that was removed."""
        return self.coordinator.data.get(self.key)

    @property
    def available(self) -> bool:
        """Mark deleted or inaccessible instances as unavailable."""
        return super().available and self.instance is not None


class IncusHostEntity(CoordinatorEntity[IncusCoordinator]):
    """Entity representing the Incus API endpoint."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IncusCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:host")},
            name=f"Incus {entry.title}",
            manufacturer="Linux Containers",
            model="Incus server",
        )
