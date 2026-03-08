"""WhatsApp session connectivity binary sensor."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import WapiClient
from .const import CONF_SESSION, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WhatsApp binary sensor from a config entry."""
    client: WapiClient = hass.data[DOMAIN][entry.entry_id]
    session_id = entry.data[CONF_SESSION]
    async_add_entities([WapiConnectedSensor(client, session_id)])


class WapiConnectedSensor(BinarySensorEntity):
    """Binary sensor: WhatsApp session connected."""

    _attr_has_entity_name = True
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:whatsapp"

    def __init__(self, client: WapiClient, session_id: str) -> None:
        self._client = client
        self._session_id = session_id
        self._attr_unique_id = f"wapi_{session_id}_connected"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, session_id)},
            "name": f"WhatsApp ({session_id})",
            "manufacturer": "wwebjs-api",
            "model": "WhatsApp Web",
            "entry_type": "service",
        }

    async def async_update(self) -> None:
        """Poll session status."""
        result = await self._client.get_session_status(self._session_id)
        self._attr_is_on = result.get("state") == "CONNECTED"
        self._attr_extra_state_attributes = {
            "session_id": self._session_id,
            "state": result.get("state"),
            "api_url": self._client.api_url,
        }
