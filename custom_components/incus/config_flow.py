"""Set up Incus from the Home Assistant user interface."""

from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from . import async_create_client
from .client import IncusAuthenticationError, IncusError, base_url
from .const import (
    CONF_CA_PATH,
    CONF_CERT_PATH,
    CONF_KEY_PATH,
    CONF_PROJECT,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_PROJECT,
    DOMAIN,
)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_CERT_PATH): str,
        vol.Required(CONF_KEY_PATH): str,
        vol.Optional(CONF_CA_PATH, default=""): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_PROJECT, default=DEFAULT_PROJECT): str,
    }
)


class IncusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure an Incus server with a trusted TLS client certificate."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Validate the remote credentials before storing a config entry."""
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_HOST] = user_input[CONF_HOST].strip().strip("[]")
            user_input[CONF_PROJECT] = (
                user_input[CONF_PROJECT].strip() or DEFAULT_PROJECT
            )

            try:
                base_url(user_input[CONF_HOST], user_input[CONF_PORT])
                client, session = await async_create_client(self.hass, user_input)
                try:
                    await client.async_test_connection(user_input[CONF_PROJECT])
                finally:
                    await session.close()
            except (aiohttp.ClientConnectorCertificateError, aiohttp.ClientSSLError):
                errors["base"] = "invalid_server_certificate"
            except IncusAuthenticationError:
                errors["base"] = "invalid_auth"
            except (TimeoutError, aiohttp.ClientError, IncusError):
                errors["base"] = "cannot_connect"
            except (OSError, ValueError):
                errors["base"] = "invalid_certificate"
            else:
                unique_id = (
                    f"{user_input[CONF_HOST].lower()}:"
                    f"{user_input[CONF_PORT]}:{user_input[CONF_PROJECT]}"
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                title = f"{user_input[CONF_HOST]} ({user_input[CONF_PROJECT]})"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)
