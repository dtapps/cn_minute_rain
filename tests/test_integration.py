"""End-to-end tests for config flow, coordinator and sensor setup (mocked API)."""

from __future__ import annotations

import voluptuous as vol
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
    DEFAULT_SCAN_INTERVAL_MINUTES,
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


def _suggested_values_from_schema(schema) -> dict:
    """从 data_schema 取出各字段的 suggested_value。"""
    out = {}
    for key in schema.schema:
        if isinstance(key, vol.Marker) and key.description:
            out[key.schema] = key.description.get("suggested_value")
    return out


async def test_user_flow_single_location(hass) -> None:
    """首次添加：经纬度/间隔写入 entry.options，data 留空。"""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LONGITUDE: 120.0,
            CONF_LATITUDE: 30.0,
            CONF_SCAN_INTERVAL: 5,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "降水 (30.00°N, 120.00°E)"
    # 地点信息统一存在 options
    assert result["data"] == {}
    assert result["options"][CONF_NAME] == "降水 (30.00°N, 120.00°E)"
    assert result["options"][CONF_LONGITUDE] == 120.0
    assert result["options"][CONF_LATITUDE] == 30.0
    assert result["options"][CONF_SCAN_INTERVAL] == 5


async def test_user_flow_prefills_ha_location(hass) -> None:
    """添加表单应以 HA 实例坐标作预填默认（避免 NumberSelector 回退显示最小值 -90/-180）。"""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    suggested = _suggested_values_from_schema(result["data_schema"])
    assert suggested[CONF_LATITUDE] == hass.config.latitude
    assert suggested[CONF_LONGITUDE] == hass.config.longitude
    assert suggested[CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL_MINUTES


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
        options={
            CONF_NAME: "测试",
            CONF_LONGITUDE: 120.0,
            CONF_LATITUDE: 30.0,
            CONF_SCAN_INTERVAL: 5,
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


async def test_options_flow_edit_location(hass, aioclient_mock) -> None:
    """打开已添加条目的“设置”(选项流)应能加载并改地点，且正确预填已存值。"""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_NAME: "测试",
            CONF_LONGITUDE: 120.0,
            CONF_LATITUDE: 30.0,
            CONF_SCAN_INTERVAL: 5,
        },
        version=1,
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(_expected_url(120.0, 30.0), json=API_RESPONSE)
    aioclient_mock.get(_expected_url(121.0, 31.0), json=API_RESPONSE)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    # 打开“设置”（标题“修改地点”）时，应回显已存储的经纬度（30/120），
    # 而不是 HA 实例所在坐标或空值。
    suggested = _suggested_values_from_schema(result["data_schema"])
    assert suggested[CONF_LATITUDE] == 30.0
    assert suggested[CONF_LONGITUDE] == 120.0

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_LONGITUDE: 121.0,
            CONF_LATITUDE: 31.0,
            CONF_SCAN_INTERVAL: 10,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_NAME] == "降水 (31.00°N, 121.00°E)"
    assert entry.options[CONF_LONGITUDE] == 121.0
    assert entry.options[CONF_LATITUDE] == 31.0
    assert entry.options[CONF_SCAN_INTERVAL] == 10
    await hass.async_block_till_done()

    # 闭环验证：改完重新打开“设置”，应回显刚保存的新经纬度（确认持久化 + 预填）
    result2 = await hass.config_entries.options.async_init(entry.entry_id)
    assert result2["type"] == FlowResultType.FORM
    suggested2 = _suggested_values_from_schema(result2["data_schema"])
    assert suggested2[CONF_LATITUDE] == 31.0
    assert suggested2[CONF_LONGITUDE] == 121.0


async def test_options_flow_shows_stored_not_ha_location(hass, aioclient_mock) -> None:
    """回归：条目里存的是用户真实地点（非 HA 坐标），打开“设置”必须回显真实值，
    而不是 HA 实例坐标（即用户报告的“纬度不是我设置的值”）。"""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_NAME: "测试",
            # 用户真实设置的地点，与 HA 实例坐标不同
            CONF_LONGITUDE: 110.0,
            CONF_LATITUDE: 21.0,
            CONF_SCAN_INTERVAL: 5,
        },
        version=1,
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(_expected_url(110.0, 21.0), json=API_RESPONSE)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    suggested = _suggested_values_from_schema(result["data_schema"])
    # 必须读到用户设置的值，而非 HA 实例坐标
    assert suggested[CONF_LATITUDE] == 21.0
    assert suggested[CONF_LONGITUDE] == 110.0
