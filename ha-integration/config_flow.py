"""Config flow for WhatsApp Notifier (wapi)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WapiClient
from .const import (
    CONF_API_KEY,
    CONF_API_URL,
    CONF_CONTACTS,
    CONF_SESSION,
    DISCOVERY_URLS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WapiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WhatsApp Notifier."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_url: str = ""
        self._api_key: str = ""
        self._session_id: str = ""
        self._needs_auth: bool = False

    async def _try_discover(self) -> str | None:
        """Try to auto-discover WhatsApp API."""
        session = async_get_clientsession(self.hass)
        for url in DISCOVERY_URLS:
            client = WapiClient(session, url)
            needs_auth = await client.ping_needs_auth()
            if needs_auth is not None:
                self._needs_auth = needs_auth
                return url
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 1: Discover or enter API URL."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_url = user_input[CONF_API_URL].rstrip("/")
            session = async_get_clientsession(self.hass)
            client = WapiClient(session, self._api_url)
            needs_auth = await client.ping_needs_auth()

            if needs_auth is None:
                errors["base"] = "cannot_connect"
            elif needs_auth:
                self._needs_auth = True
                return await self.async_step_auth()
            else:
                self._needs_auth = False
                return await self.async_step_session()
        else:
            discovered = await self._try_discover()
            if discovered:
                self._api_url = discovered
                if self._needs_auth:
                    return await self.async_step_auth()
                return await self.async_step_session()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_URL, default=self._api_url or "http://wwebjs-web-api:3001"
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={"discovery_note": "Auto-discovery failed"},
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 2: Enter API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            session = async_get_clientsession(self.hass)
            client = WapiClient(session, self._api_url, self._api_key)

            if await client.ping():
                return await self.async_step_session()
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_KEY): str}
            ),
            errors=errors,
            description_placeholders={"api_url": self._api_url},
        )

    async def async_step_session(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 3: Enter session ID."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._session_id = user_input[CONF_SESSION]

            await self.async_set_unique_id(f"wapi_{self._session_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"WhatsApp ({self._session_id})",
                data={
                    CONF_API_URL: self._api_url,
                    CONF_API_KEY: self._api_key,
                    CONF_SESSION: self._session_id,
                },
                options={CONF_CONTACTS: {}},
            )

        return self.async_show_form(
            step_id="session",
            data_schema=vol.Schema(
                {vol.Required(CONF_SESSION, default="571603685"): str}
            ),
            errors=errors,
            description_placeholders={"api_url": self._api_url},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return WapiOptionsFlow(config_entry)


class WapiOptionsFlow(OptionsFlow):
    """Handle options flow for WhatsApp Notifier."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            contacts: dict[str, str] = {}
            raw = user_input.get(CONF_CONTACTS, "")
            for line in raw.strip().splitlines():
                line = line.strip()
                if "=" in line:
                    name, chat_id = line.split("=", 1)
                    contacts[name.strip()] = chat_id.strip()

            return self.async_create_entry(
                title="",
                data={CONF_CONTACTS: contacts},
            )

        current_contacts = self._config_entry.options.get(CONF_CONTACTS, {})
        contacts_str = "\n".join(
            f"{name}={chat_id}" for name, chat_id in current_contacts.items()
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CONTACTS, default=contacts_str): str,
                }
            ),
            description_placeholders={
                "contacts_help": "One per line: Name=ChatID (e.g. Jarek=48571603685@c.us)"
            },
        )
