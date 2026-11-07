"""Metrics and status sensors for Incus instances."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import IncusCoordinator, InstanceKey
from .entity import IncusHostEntity, IncusInstanceEntity


@dataclass(frozen=True, kw_only=True)
class IncusSensorDescription(SensorEntityDescription):
    """An instance metric and its source attribute."""

    attribute: str


SENSORS = (
    IncusSensorDescription(
        key="status",
        name="Status",
        attribute="status",
    ),
    IncusSensorDescription(
        key="cpu_percent",
        name="CPU usage",
        attribute="cpu_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IncusSensorDescription(
        key="cpu_time",
        name="CPU time",
        attribute="cpu_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    IncusSensorDescription(
        key="memory_used",
        name="Memory used",
        attribute="memory_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IncusSensorDescription(
        key="memory_total",
        name="Memory total",
        attribute="memory_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IncusSensorDescription(
        key="disk_used",
        name="Root disk used",
        attribute="disk_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IncusSensorDescription(
        key="disk_total",
        name="Root disk total",
        attribute="disk_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IncusSensorDescription(
        key="network_received",
        name="Network received",
        attribute="network_received",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IncusSensorDescription(
        key="network_sent",
        name="Network sent",
        attribute="network_sent",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IncusSensorDescription(
        key="processes",
        name="Processes",
        attribute="processes",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IncusSensorDescription(
        key="uptime",
        name="Uptime",
        attribute="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


class IncusInstanceSensor(IncusInstanceEntity, SensorEntity):
    """A single runtime measurement of an Incus instance."""

    def __init__(
        self,
        coordinator: IncusCoordinator,
        entry: ConfigEntry,
        key: InstanceKey,
        description: IncusSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}:{key[0]}:{key[1]}:{description.key}"

    @property
    def native_value(self) -> float | int | str | None:
        """Return the most recent actual measurement."""
        instance = self.instance
        if instance is None:
            return None
        return getattr(instance, self.entity_description.attribute)


class IncusHostCountSensor(IncusHostEntity, SensorEntity):
    """Number of instances in the monitored project scope."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: IncusCoordinator, entry: ConfigEntry, running_only: bool
    ) -> None:
        super().__init__(coordinator, entry)
        self._running_only = running_only
        self._attr_name = "Running instances" if running_only else "Total instances"
        self._attr_unique_id = (
            f"{entry.entry_id}:host:"
            f"{'running_instances' if running_only else 'total_instances'}"
        )

    @property
    def native_value(self) -> int:
        """Count configured instances, optionally only running ones."""
        instances = self.coordinator.data.values()
        if self._running_only:
            return sum(instance.running for instance in instances)
        return len(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add current sensors and discover new instances after each poll."""
    coordinator: IncusCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[InstanceKey] = set()

    def discover() -> None:
        new = set(coordinator.data) - known
        if not new:
            return
        known.update(new)
        async_add_entities(
            IncusInstanceSensor(coordinator, entry, key, desc)
            for key in sorted(new)
            for desc in SENSORS
        )

    async_add_entities(
        [
            IncusHostCountSensor(coordinator, entry, False),
            IncusHostCountSensor(coordinator, entry, True),
        ]
    )
    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
