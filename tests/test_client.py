"""Test Incus endpoint shapes, permissions and async operations."""

import pytest

from custom_components.incus.client import (
    IncusAuthenticationError,
    IncusClient,
    IncusError,
    base_url,
)


class Response:
    def __init__(self, result, status=200):
        self.result = result
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self, content_type=None):
        return self.result


class Session:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


def client(*responses):
    session = Session(*responses)
    return IncusClient(session, "https://incus.example:8443"), session


def test_base_url_validation():
    assert base_url("::1", 8443) == "https://[::1]:8443"
    assert base_url("incus.local", 8443) == "https://incus.local:8443"
    with pytest.raises(ValueError):
        base_url("incus.local/path", 8443)


@pytest.mark.asyncio
async def test_get_instances_all_projects():
    api, session = client(Response({"type": "sync", "metadata": [{"name": "vm"}]}))
    assert await api.async_get_instances("*") == [{"name": "vm"}]
    method, url, kwargs = session.calls[0]
    assert method == "GET" and url.endswith("/1.0/instances")
    assert kwargs["params"] == {"recursion": "2", "all-projects": "true"}


@pytest.mark.asyncio
async def test_get_instances_one_project():
    api, session = client(Response({"metadata": []}))
    assert await api.async_get_instances("dev") == []
    assert session.calls[0][2]["params"] == {"recursion": "2", "project": "dev"}


@pytest.mark.asyncio
async def test_untrusted_connection_rejected():
    api, _ = client(Response({"metadata": {"auth": "untrusted"}}))
    with pytest.raises(IncusAuthenticationError):
        await api.async_test_connection("*")


@pytest.mark.asyncio
async def test_connection_test_checks_read_permission():
    api, _ = client(
        Response({"metadata": {"auth": "trusted"}}),
        Response({"type": "error", "error": "Forbidden"}, status=403),
    )
    with pytest.raises(IncusAuthenticationError):
        await api.async_test_connection("default")


@pytest.mark.asyncio
async def test_start_waits_for_result_and_scopes_project():
    api, session = client(
        Response({"type": "async", "operation": "/1.0/operations/a1"}),
        Response({"metadata": {"status_code": 200, "status": "Success"}}),
    )
    await api.async_change_state("tenant1", "vm one", "start")
    method, url, args = session.calls[0]
    assert method == "PUT"
    assert url.endswith("/1.0/instances/vm%20one/state")
    assert args["params"] == {"project": "tenant1"}
    assert args["json"]["action"] == "start"
    assert args["json"]["force"] is False
    assert session.calls[1][0] == "GET"
    assert session.calls[1][1].endswith("/1.0/operations/a1/wait")


@pytest.mark.asyncio
async def test_failed_operation_is_reported():
    api, _ = client(
        Response({"type": "async", "operation": "/1.0/operations/a1"}),
        Response({"metadata": {"status_code": 400, "err": "Instance is locked"}}),
    )
    with pytest.raises(IncusError, match="locked"):
        await api.async_change_state("default", "vm", "restart")


@pytest.mark.asyncio
async def test_reject_invalid_action():
    api, _ = client()
    with pytest.raises(ValueError):
        await api.async_change_state("default", "vm", "delete")


@pytest.mark.asyncio
async def test_reject_invalid_operation_reference():
    api, _ = client(
        Response(
            {"type": "async", "operation": "https://external.example/operations/x"}
        )
    )
    with pytest.raises(IncusError, match="did not return"):
        await api.async_change_state("default", "vm", "stop")
