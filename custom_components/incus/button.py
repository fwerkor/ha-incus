"""Explicit start, stop and restart buttons for Incus."""

from __future__ import annotations

from aiohttp import ClientError
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import IncusError
from .const import DOMAIN
from .coordinator import IncusCoordinator, InstanceKey
from .entity import IncusInstanceEntity


class IncusActionButton(IncusInstanceEntity, ButtonEntity):
    """One manually triggered Incus lifecycle action."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: IncusCoordinator,
        entry: ConfigEntry,
        key: InstanceKey,
        action: str,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._action = action
        self._attr_name = action.capitalize()
        self._attr_unique_id = f"{entry.entry_id}:{key[0]}:{key[1]}:{action}"

    @property
    def available(self) -> bool:
        """Only allow actions that match the known instance state."""
        instance = self.instance
        if not super().available or instance is None:
            return False
        return (
            instance.status.lower() == "stopped"
            if self._action == "start"
            else instance.running
        )

    async def async_press(self) -> None:
        """Perform an action and wait until Incus confirms its completion."""
        if not self.available:
            raise HomeAssistantError("Instance is not in the required state")
        try:
            await self.coordinator.client.async_change_state(
                self.key[0], self.key[1], self._action
            )
        except (TimeoutError, IncusError, ClientError) as exc:
            raise HomeAssistantError(f"Incus {self._action} failed: {exc}") from exc
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add disabled-by-default control buttons for discovered instances."""
    coordinator: IncusCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[InstanceKey] = set()

    def discover() -> None:
        new = set(coordinator.data) - known
        if new:
            known.update(new)
            async_add_entities(
                IncusActionButton(coordinator, entry, key, action)
                for key in sorted(new)
                for action in ("start", "stop", "restart")
            )

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
