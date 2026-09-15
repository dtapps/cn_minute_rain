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
    # 地点信息统一存于 entry.options（与 config_flow 一致）。旧条目可能仍在 data 里，
    # 因此读取优先级：entry.options > entry.data。
    opts = entry.options or {}
    data = entry.data or {}
    scan_interval = timedelta(
        minutes=opts.get(
            CONF_SCAN_INTERVAL,
            data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        )
    )
    loc = {
        CONF_NAME: opts.get(CONF_NAME, data.get(CONF_NAME)),
        CONF_LONGITUDE: opts.get(CONF_LONGITUDE, data.get(CONF_LONGITUDE)),
        CONF_LATITUDE: opts.get(CONF_LATITUDE, data.get(CONF_LATITUDE)),
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
