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
            CONF_LONGITUDE: 120.0,
            CONF_LATITUDE: 30.0,
            CONF_SCAN_INTERVAL: 5,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "降水 (30.00°N, 120.00°E)"
    assert result["data"][CONF_NAME] == "降水 (30.00°N, 120.00°E)"
    assert result["data"][CONF_LONGITUDE] == 120.0
    assert result["data"][CONF_LATITUDE] == 30.0
    assert result["data"][CONF_SCAN_INTERVAL] == 5


async def test_user_flow_does_not_prefill_ha_location(hass) -> None:
    """回归：首次添加表单不得把 HA 实例坐标当默认预填，否则用户直接保存会污染条目，
    导致后续“修改地点”永远回显 HA 坐标。"""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"]
    suggested = {}
    for key in schema.schema:
        if isinstance(key, vol.Marker) and key.description:
            suggested[key.schema] = key.description.get("suggested_value")
    # 经纬度不应预填成 HA 实例坐标（应为空/None，强制用户显式输入）
    assert CONF_LATITUDE not in suggested or suggested[CONF_LATITUDE] is None
    assert CONF_LONGITUDE not in suggested or suggested[CONF_LONGITUDE] is None


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
    """打开已添加条目的“设置”(选项流)应能加载并改地点，不应 500。"""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
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
    # 打开“设置”（标题“修改地点”）时，已存经纬度应作为 suggested_value 注入表单，
    # 让前端预填纬度框，而不是 HA 实例所在位置或空值。
    schema = result["data_schema"]
    suggested = {}
    for key in schema.schema:
        if isinstance(key, vol.Marker) and key.description:
            suggested[key.schema] = key.description.get("suggested_value")
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
    assert entry.data[CONF_NAME] == "降水 (31.00°N, 121.00°E)"
    assert entry.data[CONF_LONGITUDE] == 121.0
    assert entry.data[CONF_LATITUDE] == 31.0
    assert entry.data[CONF_SCAN_INTERVAL] == 10
    await hass.async_block_till_done()

    # 闭环验证：改完重新打开“设置”，应回显刚保存的新经纬度（确认持久化 + 预填）
    result2 = await hass.config_entries.options.async_init(entry.entry_id)
    assert result2["type"] == FlowResultType.FORM
    schema2 = result2["data_schema"]
    suggested2 = {}
    for key in schema2.schema:
        if isinstance(key, vol.Marker) and key.description:
            suggested2[key.schema] = key.description.get("suggested_value")
    assert suggested2[CONF_LATITUDE] == 31.0
    assert suggested2[CONF_LONGITUDE] == 121.0


async def test_options_flow_reads_from_options_when_only_in_options(
    hass, aioclient_mock
) -> None:
    """回归：早期版本把位置写进 entry.options 的条目，打开“设置”应回显 options 里的值，
    而不是 HA 实例坐标（即用户报告的“纬度不是我设置的值”）。"""
    entry = MockConfigEntry(
        domain=DOMAIN,
        # data 里没有经纬度，只有 name；真实位置存在 options 中
        data={CONF_NAME: "测试"},
        options={
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
    schema = result["data_schema"]
    suggested = {}
    for key in schema.schema:
        if isinstance(key, vol.Marker) and key.description:
            suggested[key.schema] = key.description.get("suggested_value")
    # 必须读到 options 里用户设置的值，而非 HA 实例坐标
    assert suggested[CONF_LATITUDE] == 21.0
    assert suggested[CONF_LONGITUDE] == 110.0


async def test_options_flow_prefers_data_over_poisoned_options(
    hass, aioclient_mock
) -> None:
    """回归（用户实际场景）：旧 bug 把 HA 坐标写进 entry.options 造成污染，
    打开“设置”必须回显 entry.data 里的真实地点，而非被污染的 options 值。"""
    entry = MockConfigEntry(
        domain=DOMAIN,
        # data 里是用户真实设置的地点
        data={
            CONF_NAME: "测试",
            CONF_LONGITUDE: 120.0,
            CONF_LATITUDE: 30.0,
            CONF_SCAN_INTERVAL: 5,
        },
        # options 被旧 bug 污染成 HA 实例坐标（用户报告的实际数值）
        options={
            CONF_LONGITUDE: 110.981294,
            CONF_LATITUDE: 21.517321232896705,
            CONF_SCAN_INTERVAL: 3,
        },
        version=1,
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(_expected_url(120.0, 30.0), json=API_RESPONSE)
    aioclient_mock.get(_expected_url(110.981294, 21.517321232896705), json=API_RESPONSE)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"]
    suggested = {}
    for key in schema.schema:
        if isinstance(key, vol.Marker) and key.description:
            suggested[key.schema] = key.description.get("suggested_value")
    # 必须回显 data 里的真实地点（30 / 120），而不是被污染的 options（HA 坐标）
    assert suggested[CONF_LATITUDE] == 30.0
    assert suggested[CONF_LONGITUDE] == 120.0
