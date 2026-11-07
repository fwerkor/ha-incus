"""Poll the Incus server and publish changes to all entities."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import IncusClient, IncusError
from .const import SCAN_INTERVAL
from .model import InstanceData, parse_instance

type InstanceKey = tuple[str, str]


class IncusCoordinator(DataUpdateCoordinator[dict[InstanceKey, InstanceData]]):
    """A single poll per server (including all selected projects)."""

    def __init__(self, hass, client: IncusClient, project: str, label: str) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=f"Incus {label}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.project = project
        self._previous_cpu: dict[InstanceKey, tuple[int, datetime]] = {}

    async def _async_update_data(self) -> dict[InstanceKey, InstanceData]:
        try:
            instances = await self.client.async_get_instances(self.project)
        except (ClientError, TimeoutError, IncusError) as exc:
            raise UpdateFailed(f"Unable to fetch Incus instances: {exc}") from exc

        now = datetime.now(UTC)
        result: dict[InstanceKey, InstanceData] = {}
        next_cpu: dict[InstanceKey, tuple[int, datetime]] = {}
        for raw in instances:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            key = (str(raw.get("project") or self.project), str(raw["name"]))
            data = parse_instance(
                raw, now=now, previous_cpu=self._previous_cpu.get(key)
            )
            result[key] = data
            if data.cpu_time is not None:
                next_cpu[key] = (round(data.cpu_time * 1_000_000_000), now)
        self._previous_cpu = next_cpu
        return result
