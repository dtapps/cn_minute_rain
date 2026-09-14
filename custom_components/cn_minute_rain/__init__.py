"""中国分钟级降水预报集成。"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from datetime import timedelta

from .const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import CnMinuteRainCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up cn_minute_rain from a config entry (每个条目一个地点)."""
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    scan_interval = timedelta(
        minutes=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
    )
    loc = {
        CONF_NAME: entry.data[CONF_NAME],
        CONF_LONGITUDE: entry.data[CONF_LONGITUDE],
        CONF_LATITUDE: entry.data[CONF_LATITUDE],
    }
    coord = CnMinuteRainCoordinator(hass, session, loc, scan_interval)
    await coord.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coord
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
