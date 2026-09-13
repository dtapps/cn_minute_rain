"""中国分钟级降水预报集成。"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCATIONS, DOMAIN, PLATFORMS
from .coordinator import CnMinuteRainCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up cn_minute_rain from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    coordinators = []
    for loc in entry.data[CONF_LOCATIONS]:
        coord = CnMinuteRainCoordinator(hass, session, loc)
        await coord.async_config_entry_first_refresh()
        coordinators.append(coord)
    hass.data[DOMAIN][entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
