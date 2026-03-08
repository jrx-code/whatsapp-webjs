"""WhatsApp test message buttons — one per configured contact."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import WapiClient
from .const import CONF_CONTACTS, CONF_SESSION, DOMAIN

_LOGGER = logging.getLogger(__name__)

TEST_MESSAGE = "WhatsApp Notifier test message — integration is working."


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WhatsApp test buttons from a config entry."""
    client: WapiClient = hass.data[DOMAIN][entry.entry_id]
    session_id = entry.data[CONF_SESSION]
    contacts = entry.options.get(CONF_CONTACTS, {})

    entities = [
        WapiTestButton(client, session_id, name, chat_id)
        for name, chat_id in contacts.items()
    ]

    if entities:
        async_add_entities(entities)


class WapiTestButton(ButtonEntity):
    """Button to send a test message to a contact."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:message-check-outline"

    def __init__(
        self,
        client: WapiClient,
        session_id: str,
        contact_name: str,
        chat_id: str,
    ) -> None:
        self._client = client
        self._session_id = session_id
        self._chat_id = chat_id
        slug = contact_name.lower().replace(" ", "_")
        self._attr_unique_id = f"wapi_{session_id}_test_{slug}"
        self._attr_name = f"Test {contact_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, session_id)},
            "name": f"WhatsApp ({session_id})",
            "manufacturer": "wwebjs-api",
            "model": "WhatsApp Web",
            "entry_type": "service",
        }

    async def async_press(self) -> None:
        """Send a test message."""
        ok = await self._client.send_message(
            self._session_id, self._chat_id, TEST_MESSAGE
        )
        if ok:
            _LOGGER.info("Test message sent to %s", self._chat_id)
        else:
            _LOGGER.warning("Failed to send test message to %s", self._chat_id)
