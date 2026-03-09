"""WhatsApp notify entities via wwebjs-api."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .api import WapiClient
from .const import ATTR_MEDIA_URL, CONF_CONTACTS, CONF_SESSION, DOMAIN

CONF_URL = "url"
CONF_TOKEN = "token"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_SESSION): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
    },
)

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
    """Main WhatsApp notify entity — supports target in service data."""

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
        """Send a WhatsApp message to target(s) specified in data."""
        data = kwargs.get("data") or {}
        targets = kwargs.get("target") or data.get("target")
        if not targets:
            _LOGGER.warning("No target specified for WhatsApp message")
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


# --- Legacy YAML platform (backward compat for automations) ---

TIMEOUT = aiohttp.ClientTimeout(total=30)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> WapiNotificationService:
    """Get the legacy wapi notification service."""
    return WapiNotificationService(
        hass,
        config[CONF_URL],
        config[CONF_SESSION],
        config.get(CONF_TOKEN),
    )


class WapiNotificationService(BaseNotificationService):
    """Legacy notify service — supports target in service call."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        session: str,
        token: str | None = None,
    ) -> None:
        self.hass = hass
        self._url = url.rstrip("/")
        self._session = session
        self._token = token

    async def _send(self, data: dict[str, Any]) -> None:
        url = f"{self._url}/{self._session}"
        headers: dict[str, str] = {}
        if self._token:
            headers["x-api-key"] = self._token

        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                url, json=data, headers=headers, timeout=TIMEOUT
            ) as resp:
                resp.raise_for_status()
        except aiohttp.ClientError as ex:
            _LOGGER.error("Error sending wapi notification: %s", ex)

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        targets = kwargs.get(ATTR_TARGET)
        if not targets:
            _LOGGER.error("No target specified for wapi notification")
            return

        title = kwargs.get(ATTR_TITLE)
        data = kwargs.get(ATTR_DATA)
        content = f"*{title}*\n{message}" if title else message

        for chat_id in targets:
            if content:
                await self._send(
                    {"content": content, "chatId": chat_id, "contentType": "string"}
                )
            media_url = data.get("media_url") if data else None
            if media_url:
                for url in media_url.splitlines():
                    if url.strip():
                        await self._send(
                            {"content": url.strip(), "chatId": chat_id, "contentType": "MessageMediaFromURL"}
                        )
