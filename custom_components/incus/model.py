"""Convert Incus instance information into stable, typed measurements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class InstanceData:
    """A single snapshot of one instance."""

    project: str
    name: str
    kind: str
    location: str
    status: str
    cpu_time: float | None
    cpu_percent: float | None
    memory_used: int | None
    memory_total: int | None
    disk_used: int | None
    disk_total: int | None
    network_received: int | None
    network_sent: int | None
    processes: int | None
    uptime: int | None

    @property
    def running(self) -> bool:
        """Whether the instance is currently running."""
        return self.status.lower() == "running"


def _number(value: Any) -> int | None:
    """Preserve missing values instead of reporting them as zero."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _sum_network(network: dict, counter: str) -> int | None:
    numbers = [
        _number(interface.get("counters", {}).get(counter))
        for name, interface in network.items()
        if name != "lo" and isinstance(interface, dict)
    ]
    numbers = [value for value in numbers if value is not None]
    return sum(numbers) if numbers else None


def _uptime(state: dict, instance: dict, now: datetime) -> int | None:
    timestamp = state.get("started_at") or instance.get("last_used_at")
    if not timestamp:
        return None
    try:
        started = datetime.fromisoformat(timestamp)
        if started.tzinfo is None or started.year < 2000:
            return None
        return max(0, int((now - started).total_seconds()))
    except (ValueError, TypeError, OverflowError):
        return None


def parse_instance(
    raw: dict,
    *,
    now: datetime | None = None,
    previous_cpu: tuple[int, datetime] | None = None,
) -> InstanceData:
    """Parse the API's recursion=2 InstanceFull representation."""
    now = now or datetime.now(UTC)
    state = raw.get("state") or {}
    status = str(state.get("status") or raw.get("status") or "Unknown")
    running = status.lower() == "running"
    cpu = state.get("cpu") or {}
    memory = state.get("memory") or {}
    disks = state.get("disk") or {}
    root = disks.get("root") or {}
    network = state.get("network") or {}
    cpu_ns = _number(cpu.get("usage")) if running else None
    allocated_ns = _number(cpu.get("allocated_time"))
    cpu_pct = None
    if cpu_ns is not None and allocated_ns and previous_cpu:
        previous_ns, previous_time = previous_cpu
        elapsed = (now - previous_time).total_seconds()
        if elapsed > 0 and cpu_ns >= previous_ns:
            cpu_pct = round(
                max(0.0, (cpu_ns - previous_ns) / (elapsed * allocated_ns) * 100),
                2,
            )

    return InstanceData(
        project=str(raw.get("project") or "default"),
        name=str(raw["name"]),
        kind=str(raw.get("type") or "container"),
        location=str(raw.get("location") or ""),
        status=status,
        cpu_time=cpu_ns / 1_000_000_000 if cpu_ns is not None else None,
        cpu_percent=cpu_pct,
        memory_used=_number(memory.get("usage")) if running else None,
        memory_total=_number(memory.get("total")) if running else None,
        disk_used=_number(root.get("usage")) if running else None,
        disk_total=_number(root.get("total")) if running else None,
        network_received=_sum_network(network, "bytes_received") if running else None,
        network_sent=_sum_network(network, "bytes_sent") if running else None,
        processes=_number(state.get("processes")) if running else None,
        uptime=_uptime(state, raw, now) if running else None,
    )
