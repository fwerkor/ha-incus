"""Power switches for Incus containers and virtual machines."""

from __future__ import annotations

from aiohttp import ClientError
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import IncusError
from .const import DOMAIN
from .coordinator import IncusCoordinator, InstanceKey
from .entity import IncusInstanceEntity


class IncusPowerSwitch(IncusInstanceEntity, SwitchEntity):
    """Turn an Incus container or VM on or off."""

    _attr_name = "Power"

    def __init__(
        self, coordinator: IncusCoordinator, entry: ConfigEntry, key: InstanceKey
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_unique_id = f"{entry.entry_id}:{key[0]}:{key[1]}:power"

    @property
    def is_on(self) -> bool | None:
        """Return whether the instance is running."""
        return self.instance.running if self.instance else None

    async def _change_state(self, action: str) -> None:
        if not self.available:
            raise HomeAssistantError("Instance is unavailable")
        try:
            await self.coordinator.client.async_change_state(
                self.key[0], self.key[1], action
            )
        except (TimeoutError, IncusError, ClientError) as exc:
            raise HomeAssistantError(f"Incus {action} failed: {exc}") from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        """Start the instance."""
        await self._change_state("start")

    async def async_turn_off(self, **kwargs) -> None:
        """Gracefully stop the instance."""
        await self._change_state("stop")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a power switch for each instance, including new ones."""
    coordinator: IncusCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[InstanceKey] = set()

    def discover() -> None:
        new = set(coordinator.data) - known
        if new:
            known.update(new)
            async_add_entities(
                IncusPowerSwitch(coordinator, entry, key) for key in sorted(new)
            )

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
