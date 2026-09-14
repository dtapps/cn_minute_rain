"""End-to-end tests for config flow, coordinator and sensor setup (mocked API)."""
from __future__ import annotations

from datetime import timedelta
from yarl import URL

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cn_minute_rain.coordinator import CnMinuteRainCoordinator
from custom_components.cn_minute_rain.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

API_URL = "https://mpf.weather.com.cn/mpf_v3/webgis/minute"
API_RESPONSE = {
    "msg": "未来2小时不会降雨",
    "values": [0, 0, 0, 0, 0],
    "time": "20240101000000",
}


def _expected_url(lon: float, lat: float) -> str:
    return str(URL(API_URL).with_query(lon=lon, lat=lat))


async def test_user_flow_single_location(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "测试",
            CONF_LONGITUDE: 120.0,
            CONF_LATITUDE: 30.0,
            CONF_SCAN_INTERVAL: 300,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "测试"
    assert result["data"][CONF_NAME] == "测试"
    assert result["data"][CONF_LONGITUDE] == 120.0
    assert result["data"][CONF_LATITUDE] == 30.0
    assert result["data"][CONF_SCAN_INTERVAL] == 300


async def test_coordinator_update(hass, aioclient_mock) -> None:
    loc = {CONF_NAME: "测试", CONF_LONGITUDE: 120.0, CONF_LATITUDE: 30.0}
    coord = CnMinuteRainCoordinator(
        hass, async_get_clientsession(hass), loc, timedelta(seconds=300)
    )
    aioclient_mock.get(_expected_url(120.0, 30.0), json=API_RESPONSE)

    data = await coord._async_update_data()

    assert data["msg"] == "未来2小时不会降雨"
    assert data["values"] == [0.0, 0.0, 0.0, 0.0, 0.0]
    assert data["name"] == "测试"
    assert data["longitude"] == 120.0


async def test_sensor_setup(hass, aioclient_mock) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "测试",
            CONF_LONGITUDE: 120.0,
            CONF_LATITUDE: 30.0,
            CONF_SCAN_INTERVAL: 300,
        },
        version=1,
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(_expected_url(120.0, 30.0), json=API_RESPONSE)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_entity_ids("sensor")
    assert len(states) == 2
    for entity_id in states:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state is not None
