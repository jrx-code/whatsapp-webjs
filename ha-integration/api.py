"""WhatsApp API client for wwebjs-api."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


class WapiClient:
    """Async client for wwebjs-api."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_url: str,
        api_key: str | None = None,
    ) -> None:
        self._session = session
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key

    @property
    def api_url(self) -> str:
        return self._api_url

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    async def ping(self) -> bool:
        """Check API availability. Returns True if API responds."""
        try:
            async with self._session.get(
                f"{self._api_url}/ping",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, TimeoutError):
            return False

    async def ping_needs_auth(self) -> bool | None:
        """Check if API requires authentication.

        Returns True if auth required, False if not, None if unreachable.
        """
        try:
            async with self._session.get(
                f"{self._api_url}/ping",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return False
                if resp.status == 403:
                    return True
                return None
        except (aiohttp.ClientError, TimeoutError):
            return None

    async def get_sessions(self) -> list[str]:
        """List all session IDs from the API."""
        try:
            async with self._session.get(
                f"{self._api_url}/session/getSessions",
                headers=self._headers(),
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        return data.get("result", [])
                return []
        except (aiohttp.ClientError, TimeoutError):
            return []

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        """Get session status."""
        try:
            async with self._session.get(
                f"{self._api_url}/session/status/{session_id}",
                headers=self._headers(),
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as ex:
            _LOGGER.debug("Failed to get session status: %s", ex)
            return {"success": False, "message": str(ex)}

    async def send_message(
        self,
        session_id: str,
        chat_id: str,
        content: str,
        content_type: str = "string",
    ) -> bool:
        """Send a message via WhatsApp."""
        payload = {
            "chatId": chat_id,
            "content": content,
            "contentType": content_type,
        }
        try:
            async with self._session.post(
                f"{self._api_url}/client/sendMessage/{session_id}",
                json=payload,
                headers=self._headers(),
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                if resp.status == 200:
                    _LOGGER.debug("Message sent to %s", chat_id)
                    return True
                body = await resp.text()
                _LOGGER.error(
                    "Failed to send message: %s %s", resp.status, body
                )
                return False
        except (aiohttp.ClientError, TimeoutError) as ex:
            _LOGGER.error("Error sending message: %s", ex)
            return False

    async def send_media(
        self,
        session_id: str,
        chat_id: str,
        media_url: str,
    ) -> bool:
        """Send media via URL."""
        return await self.send_message(
            session_id, chat_id, media_url, "MessageMediaFromURL"
        )
