"""Home Assistant integration for Incus servers."""

from __future__ import annotations

import logging
import ssl

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import IncusClient, base_url, create_ssl_context
from .const import (
    CONF_CA_PATH,
    CONF_CERT_PATH,
    CONF_KEY_PATH,
    CONF_PROJECT,
    CONF_VERIFY_SSL,
    DEFAULT_PROJECT,
    DOMAIN,
)
from .coordinator import IncusCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SWITCH]


def certificate_paths(hass: HomeAssistant, data: dict) -> tuple[str, str, str | None]:
    """Resolve paths relative to the Home Assistant config directory."""

    def resolve(value: str) -> str:
        return value if value.startswith("/") else hass.config.path(value)

    ca_path = data.get(CONF_CA_PATH)
    return (
        resolve(data[CONF_CERT_PATH]),
        resolve(data[CONF_KEY_PATH]),
        resolve(ca_path) if ca_path else None,
    )


async def async_create_client(
    hass: HomeAssistant, data: dict
) -> tuple[IncusClient, aiohttp.ClientSession]:
    """Build an independently authenticated HTTP session for an Incus host."""
    cert_path, key_path, ca_path = certificate_paths(hass, data)
    context = await hass.async_add_executor_job(
        create_ssl_context,
        cert_path,
        key_path,
        ca_path,
        data.get(CONF_VERIFY_SSL, True),
    )
    session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=context),
        raise_for_status=False,
    )
    return IncusClient(session, base_url(data[CONF_HOST], data[CONF_PORT])), session


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a configured Incus endpoint."""
    try:
        client, session = await async_create_client(hass, entry.data)
    except (OSError, ssl.SSLError, ValueError) as exc:
        raise ConfigEntryNotReady(f"Incus TLS configuration error: {exc}") from exc

    coordinator = IncusCoordinator(
        hass,
        client,
        entry.data.get(CONF_PROJECT, DEFAULT_PROJECT),
        entry.title,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        await session.close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platform entities before closing the API session."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.client._session.close()
    return True
