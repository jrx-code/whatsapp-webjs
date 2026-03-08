"""WhatsApp notify entities via wwebjs-api."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import WapiClient
from .const import ATTR_MEDIA_URL, CONF_CONTACTS, CONF_SESSION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WhatsApp notify entities from a config entry."""
    client: WapiClient = hass.data[DOMAIN][entry.entry_id]
    session_id = entry.data[CONF_SESSION]
    contacts = entry.options.get(CONF_CONTACTS, {})

    entities: list[NotifyEntity] = [
        WapiNotifyEntity(client, session_id, entry),
    ]

    for name, chat_id in contacts.items():
        entities.append(
            WapiContactNotifyEntity(client, session_id, entry, name, chat_id)
        )

    async_add_entities(entities)


class WapiNotifyEntity(NotifyEntity):
    """Main WhatsApp notify entity — send to any target."""

    _attr_has_entity_name = True
    _attr_name = "WhatsApp"
    _attr_icon = "mdi:whatsapp"

    def __init__(
        self,
        client: WapiClient,
        session_id: str,
        entry: ConfigEntry,
    ) -> None:
        self._client = client
        self._session_id = session_id
        self._attr_unique_id = f"wapi_{session_id}_notify"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, session_id)},
            "name": f"WhatsApp ({session_id})",
            "manufacturer": "wwebjs-api",
            "model": "WhatsApp Web",
            "entry_type": "service",
        }

    async def async_send_message(self, message: str, title: str | None = None, **kwargs: Any) -> None:
        """Send a WhatsApp message. Requires 'target' in data."""
        data = kwargs.get("data") or {}
        targets = data.get("target")
        if not targets:
            _LOGGER.error("No target specified — pass 'target' in data (e.g. '48886108986@c.us')")
            return

        if isinstance(targets, str):
            targets = [targets]

        content = f"*{title}*\n{message}" if title else message

        for chat_id in targets:
            if content:
                await self._client.send_message(
                    self._session_id, chat_id, content
                )

            media_url = data.get(ATTR_MEDIA_URL)
            if media_url:
                for url in media_url.splitlines():
                    url = url.strip()
                    if url:
                        await self._client.send_media(
                            self._session_id, chat_id, url
                        )


class WapiContactNotifyEntity(NotifyEntity):
    """Pre-configured contact notify entity — no target needed."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:whatsapp"

    def __init__(
        self,
        client: WapiClient,
        session_id: str,
        entry: ConfigEntry,
        contact_name: str,
        chat_id: str,
    ) -> None:
        self._client = client
        self._session_id = session_id
        self._chat_id = chat_id
        self._contact_name = contact_name
        slug = contact_name.lower().replace(" ", "_")
        self._attr_unique_id = f"wapi_{session_id}_{slug}"
        self._attr_name = f"WhatsApp {contact_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, session_id)},
            "name": f"WhatsApp ({session_id})",
            "manufacturer": "wwebjs-api",
            "model": "WhatsApp Web",
            "entry_type": "service",
        }

    async def async_send_message(self, message: str, title: str | None = None, **kwargs: Any) -> None:
        """Send a WhatsApp message to the pre-configured contact."""
        content = f"*{title}*\n{message}" if title else message

        data = kwargs.get("data") or {}

        if content:
            await self._client.send_message(
                self._session_id, self._chat_id, content
            )

        media_url = data.get(ATTR_MEDIA_URL)
        if media_url:
            for url in media_url.splitlines():
                url = url.strip()
                if url:
                    await self._client.send_media(
                        self._session_id, self._chat_id, url
                    )
