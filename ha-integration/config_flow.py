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

    def _reuse_existing_credentials(self) -> bool:
        """Copy api_url and api_key from an existing wapi config entry."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            self._api_url = entry.data[CONF_API_URL]
            self._api_key = entry.data.get(CONF_API_KEY, "")
            return True
        return False

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
            # If another wapi entry exists, reuse its credentials
            if self._reuse_existing_credentials():
                return await self.async_step_session()

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
        """Step 3: Select or enter session ID."""
        errors: dict[str, str] = {}
        NEW_SESSION = "__new__"

        if user_input is not None:
            choice = user_input[CONF_SESSION]
            if choice == NEW_SESSION:
                return await self.async_step_session_manual()

            self._session_id = choice
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

        # Fetch available sessions from API
        session = async_get_clientsession(self.hass)
        client = WapiClient(session, self._api_url, self._api_key)
        all_sessions = await client.get_sessions()

        # Filter out already configured sessions
        configured = {
            e.data[CONF_SESSION]
            for e in self.hass.config_entries.async_entries(DOMAIN)
        }
        available = [s for s in all_sessions if s not in configured]

        options: dict[str, str] = {}
        for sid in available:
            status = await client.get_session_status(sid)
            state = status.get("state", "unknown")
            options[sid] = f"{sid} ({state})"
        options[NEW_SESSION] = "— Enter new session ID —"

        return self.async_show_form(
            step_id="session",
            data_schema=vol.Schema(
                {vol.Required(CONF_SESSION): vol.In(options)}
            ),
            errors=errors,
            description_placeholders={"api_url": self._api_url},
        )

    async def async_step_session_manual(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step 3b: Manually enter session ID."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._session_id = user_input[CONF_SESSION].strip()

            if not self._session_id:
                errors["base"] = "empty_fields"
            else:
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
            step_id="session_manual",
            data_schema=vol.Schema(
                {vol.Required(CONF_SESSION): str}
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
        """Show current contacts and offer add/remove."""
        current_contacts = self._config_entry.options.get(CONF_CONTACTS, {})

        if user_input is not None:
            action = user_input.get("action", "done")
            if action == "add":
                return await self.async_step_add_contact()
            if action == "remove" and current_contacts:
                return await self.async_step_remove_contact()
            return self.async_create_entry(title="", data=self._config_entry.options)

        contact_list = ", ".join(current_contacts.keys()) if current_contacts else "—"

        actions = ["done", "add"]
        if current_contacts:
            actions.append("remove")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="done"): vol.In(
                        {
                            "done": "Save & close",
                            "add": "Add contact",
                            **({"remove": "Remove contact"} if current_contacts else {}),
                        }
                    ),
                }
            ),
            description_placeholders={"contacts_list": contact_list},
        )

    async def async_step_add_contact(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Add a new contact."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input["contact_name"].strip()
            chat_id = user_input["chat_id"].strip()

            if not name or not chat_id:
                errors["base"] = "empty_fields"
            elif not chat_id.endswith("@c.us"):
                chat_id = f"{chat_id}@c.us"

            if not errors:
                contacts = dict(self._config_entry.options.get(CONF_CONTACTS, {}))
                contacts[name] = chat_id
                return self.async_create_entry(
                    title="", data={CONF_CONTACTS: contacts}
                )

        return self.async_show_form(
            step_id="add_contact",
            data_schema=vol.Schema(
                {
                    vol.Required("contact_name"): str,
                    vol.Required("chat_id"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_remove_contact(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Remove an existing contact."""
        current_contacts = self._config_entry.options.get(CONF_CONTACTS, {})

        if user_input is not None:
            name = user_input["contact_name"]
            contacts = dict(current_contacts)
            contacts.pop(name, None)
            return self.async_create_entry(
                title="", data={CONF_CONTACTS: contacts}
            )

        return self.async_show_form(
            step_id="remove_contact",
            data_schema=vol.Schema(
                {
                    vol.Required("contact_name"): vol.In(
                        {n: f"{n} ({cid})" for n, cid in current_contacts.items()}
                    ),
                }
            ),
        )
