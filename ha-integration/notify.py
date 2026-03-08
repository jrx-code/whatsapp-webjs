"""WhatsApp Notifier via wwebjs-api."""

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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_URL = "url"
CONF_SESSION = "session"
CONF_TOKEN = "token"

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_SESSION): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
    },
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> WapiNotificationService:
    """Get the wapi notification service."""
    return WapiNotificationService(
        hass,
        config[CONF_URL],
        config[CONF_SESSION],
        config.get(CONF_TOKEN),
    )


class WapiNotificationService(BaseNotificationService):
    """Send notifications via wwebjs-api."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        session: str,
        token: str | None = None,
    ) -> None:
        """Initialize the service."""
        self.hass = hass
        self._url = url.rstrip("/")
        self._session = session
        self._token = token

    async def _send(self, data: dict[str, Any]) -> None:
        """Send a single request to the wwebjs-api."""
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
                _LOGGER.debug("Message sent to %s", data.get("chatId"))
        except aiohttp.ClientError as ex:
            _LOGGER.error("Error sending wapi notification: %s", ex)

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a WhatsApp message."""
        targets = kwargs.get(ATTR_TARGET)
        if not targets:
            _LOGGER.error("No target (chatId) specified for wapi notification")
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
                            {
                                "content": url.strip(),
                                "chatId": chat_id,
                                "contentType": "MessageMediaFromURL",
                            }
                        )
