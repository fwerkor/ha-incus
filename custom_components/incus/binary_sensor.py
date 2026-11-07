"""Running-state binary sensor for Incus instances."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import IncusCoordinator, InstanceKey
from .entity import IncusInstanceEntity


class IncusRunningSensor(IncusInstanceEntity, BinarySensorEntity):
    """True while the instance is running."""

    _attr_name = "Running"

    def __init__(
        self,
        coordinator: IncusCoordinator,
        entry: ConfigEntry,
        key: InstanceKey,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_unique_id = f"{entry.entry_id}:{key[0]}:{key[1]}:running"

    @property
    def is_on(self) -> bool | None:
        """Return the running state."""
        return self.instance.running if self.instance else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a binary sensor for each instance, including new instances."""
    coordinator: IncusCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[InstanceKey] = set()

    def discover() -> None:
        new = set(coordinator.data) - known
        if new:
            known.update(new)
            async_add_entities(
                IncusRunningSensor(coordinator, entry, key) for key in sorted(new)
            )

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
