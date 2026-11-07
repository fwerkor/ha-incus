"""Tests for Incus instance-state parsing."""

from datetime import UTC, datetime, timedelta

from custom_components.incus.model import parse_instance

NOW = datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC)


def _instance():
    return {
        "name": "demo",
        "project": "tenant1",
        "type": "virtual-machine",
        "location": "node1",
        "status": "Running",
        "state": {
            "status": "Running",
            "started_at": "2026-11-07T10:00:00Z",
            "cpu": {"usage": 4_000_000_000, "allocated_time": 2_000_000_000},
            "memory": {"usage": 1_024, "total": 4_096},
            "disk": {"root": {"usage": 2_048, "total": 8_192}},
            "network": {
                "eth0": {"counters": {"bytes_received": 20, "bytes_sent": 30}},
                "eth1": {"counters": {"bytes_received": 40, "bytes_sent": 10}},
                "lo": {"counters": {"bytes_received": 100, "bytes_sent": 100}},
            },
            "processes": 40,
        },
    }


def test_running_instance_metrics():
    result = parse_instance(_instance(), now=NOW)
    assert (result.project, result.name, result.kind) == (
        "tenant1",
        "demo",
        "virtual-machine",
    )
    assert result.running
    assert result.cpu_time == 4
    assert result.cpu_percent is None
    assert result.memory_used == 1024
    assert result.disk_total == 8192
    assert result.network_received == 60
    assert result.network_sent == 40
    assert result.uptime == 7200


def test_cpu_percentage_requires_two_samples():
    result = parse_instance(
        _instance(),
        now=NOW,
        previous_cpu=(2_000_000_000, NOW - timedelta(seconds=1)),
    )
    assert result.cpu_percent == 100


def test_stopped_instance_has_no_runtime_metrics():
    instance = _instance()
    instance["status"] = "Stopped"
    instance["state"] = {"status": "Stopped"}
    result = parse_instance(instance, now=NOW)
    assert not result.running
    assert result.cpu_time is None
    assert result.memory_used is None
    assert result.network_received is None
    assert result.uptime is None


def test_missing_metrics_are_unknown():
    result = parse_instance(
        {"name": "simple", "project": "default", "status": "Running"},
        now=NOW,
    )
    assert result.running
    assert result.memory_total is None
    assert result.disk_used is None
    assert result.network_sent is None


def test_cpu_time_reset_does_not_report_negative_percentage():
    result = parse_instance(_instance(), now=NOW, previous_cpu=(8_000_000_000, NOW))
    assert result.cpu_percent is None


def test_bad_start_timestamp_is_ignored():
    raw = _instance()
    raw["state"]["started_at"] = "not-a-date"
    assert parse_instance(raw, now=NOW).uptime is None
