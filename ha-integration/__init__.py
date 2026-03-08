"""WhatsApp Notifier integration (wapi)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WapiClient
from .const import CONF_API_KEY, CONF_API_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NOTIFY]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WhatsApp Notifier from a config entry."""
    session = async_get_clientsession(hass)
    client = WapiClient(
        session,
        entry.data[CONF_API_URL],
        entry.data.get(CONF_API_KEY),
    )

    if not await client.ping():
        _LOGGER.warning("WhatsApp API not reachable at %s", entry.data[CONF_API_URL])

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload entry to pick up new contacts."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
