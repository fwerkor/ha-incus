"""Small asynchronous client for the Incus REST API."""

from __future__ import annotations

import json as jsonlib
import ssl
from collections.abc import Mapping
from urllib.parse import quote

import aiohttp


class IncusError(Exception):
    """An Incus API error."""


class IncusAuthenticationError(IncusError):
    """Incus rejected our client certificate or permissions."""


def create_ssl_context(
    cert_path: str, key_path: str, ca_path: str | None, verify_ssl: bool
) -> ssl.SSLContext:
    """Create a TLS context with a client certificate (never persisted here)."""
    context = ssl.create_default_context(cafile=ca_path or None)
    if not verify_ssl:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return context


def base_url(host: str, port: int) -> str:
    """Handle IPv6 addresses as well as ordinary hostnames."""
    host = host.strip().strip("[]")
    if not host or any(char in host for char in "/\\@?#"):
        raise ValueError("Invalid Incus host")
    if ":" in host:
        host = f"[{host}]"
    return f"https://{host}:{port}"


class IncusClient:
    """Authenticated requests to one Incus server."""

    def __init__(self, session: aiohttp.ClientSession, url: str) -> None:
        self._session = session
        self._url = url.rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: dict | None = None,
        timeout: int = 25,
    ) -> dict:
        try:
            async with self._session.request(
                method,
                f"{self._url}{path}",
                params=params,
                json=json,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                payload = await response.json(content_type=None)
                if not isinstance(payload, dict):
                    raise IncusError("Unexpected Incus response")
                if response.status in (401, 403):
                    raise IncusAuthenticationError(
                        payload.get("error") or "Incus authentication failed"
                    )
                if response.status >= 400 or payload.get("type") == "error":
                    raise IncusError(
                        payload.get("error") or f"Incus returned HTTP {response.status}"
                    )
                return payload
        except (aiohttp.ContentTypeError, jsonlib.JSONDecodeError) as exc:
            raise IncusError("Incus returned a non-JSON response") from exc

    async def async_test_connection(self, project: str) -> dict:
        """Verify that this client is trusted and can list the chosen instances."""
        server = await self._request("GET", "/1.0")
        metadata = server.get("metadata") or {}
        if metadata.get("auth") == "untrusted":
            raise IncusAuthenticationError("Client certificate is not trusted by Incus")
        await self.async_get_instances(project)
        return metadata

    async def async_get_instances(self, project: str) -> list[dict]:
        """Fetch full instance records including their runtime state."""
        params = {"recursion": "2"}
        if project == "*":
            params["all-projects"] = "true"
        else:
            params["project"] = project
        response = await self._request("GET", "/1.0/instances", params=params)
        instances = response.get("metadata")
        if not isinstance(instances, list):
            raise IncusError("Instance list was not an array")
        return instances

    async def async_change_state(self, project: str, name: str, action: str) -> None:
        """Start, stop or restart and wait for the actual operation outcome."""
        if action not in {"start", "stop", "restart"}:
            raise ValueError("Unsupported instance action")
        result = await self._request(
            "PUT",
            f"/1.0/instances/{quote(name, safe='')}/state",
            params={"project": project},
            json={"action": action, "timeout": 30, "force": False},
        )
        if result.get("type") == "sync":
            return

        operation = result.get("operation")
        if not isinstance(operation, str) or not operation.startswith(
            "/1.0/operations/"
        ):
            raise IncusError("Incus did not return an operation to track")
        operation = operation.split("?", 1)[0]
        result = await self._request(
            "GET",
            f"{operation}/wait",
            params={"project": project, "timeout": "60"},
            timeout=75,
        )
        details = result.get("metadata") or {}
        if not isinstance(details, dict):
            raise IncusError("Invalid Incus operation response")
        code = details.get("status_code")
        if code != 200:
            raise IncusError(
                details.get("err") or details.get("status") or "Incus operation failed"
            )
