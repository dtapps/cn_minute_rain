"""端到端测试：配置流 / 选项流 / 条目生命周期（接口全部 mock）。"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.cn_minute_rain import async_unload_entry
from custom_components.cn_minute_rain.config_flow import _format_name
from custom_components.cn_minute_rain.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)
from custom_components.cn_minute_rain.coordinator import CnMinuteRainCoordinator


def _suggested_values_from_schema(schema) -> dict:
    """从 data_schema 取出各字段的 suggested_value。"""
    out = {}
    for key in schema.schema:
        if isinstance(key, vol.Marker) and key.description:
            out[key.schema] = key.description.get("suggested_value")
    return out


# ==========================================================================
# 配置流：首次添加
# ==========================================================================


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
    """添加表单应以 HA 实例坐标作预填默认（避免 NumberSelector 回退显示最小值）。"""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    suggested = _suggested_values_from_schema(result["data_schema"])
    assert suggested[CONF_LATITUDE] == hass.config.latitude
    assert suggested[CONF_LONGITUDE] == hass.config.longitude
    assert suggested[CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL_MINUTES


@pytest.mark.parametrize(
    ("bad_input", "bad_field"),
    [
        pytest.param(
            {CONF_LONGITUDE: 181.0, CONF_LATITUDE: 30.0, CONF_SCAN_INTERVAL: 5},
            "longitude",
            id="longitude-out-of-range",
        ),
        pytest.param(
            {CONF_LONGITUDE: 120.0, CONF_LATITUDE: 91.0, CONF_SCAN_INTERVAL: 5},
            "latitude",
            id="latitude-out-of-range",
        ),
        pytest.param(
            {CONF_LONGITUDE: 120.0, CONF_LATITUDE: 30.0, CONF_SCAN_INTERVAL: 0},
            "scan_interval",
            id="scan-interval-zero",
        ),
    ],
)
async def test_user_flow_rejects_out_of_range(hass, bad_input, bad_field) -> None:
    """NumberSelector 的 min/max 必须在后端生效，不能只靠前端拦。"""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with pytest.raises(InvalidData) as err:
        await hass.config_entries.flow.async_configure(result["flow_id"], bad_input)

    assert bad_field in str(err.value.path)


# ==========================================================================
# 命名：南半球 / 西经 / 赤道都不能拼错
# ==========================================================================


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [
        pytest.param(30.0, 120.0, "降水 (30.00°N, 120.00°E)", id="north-east"),
        pytest.param(-33.25, -70.5, "降水 (33.25°S, 70.50°W)", id="south-west"),
        pytest.param(0.0, 0.0, "降水 (0.00°N, 0.00°E)", id="equator-prime"),
        pytest.param(-0.5, 0.5, "降水 (0.50°S, 0.50°E)", id="mixed"),
    ],
)
def test_format_name(latitude, longitude, expected) -> None:
    assert _format_name(latitude, longitude) == expected


# ==========================================================================
# 条目 setup / 卸载 / 多地点
# ==========================================================================


async def test_setup_uses_unverified_ssl_session(
    hass, aioclient_mock, api_url, api_payload, make_entry
) -> None:
    """中国天气网证书偶尔过期，setup 必须拿 verify_ssl=False 的会话。"""
    entry = make_entry()
    aioclient_mock.get(api_url(120.0, 30.0), json=api_payload)

    with patch(
        "custom_components.cn_minute_rain.async_get_clientsession",
        wraps=async_get_clientsession,
    ) as spy:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    spy.assert_called_once_with(hass, verify_ssl=False)


async def test_setup_retries_when_api_is_down(
    hass, aioclient_mock, api_url, make_entry
) -> None:
    """接口挂掉时不能 setup 成功留一排空实体，要进 SETUP_RETRY 等自动重试。"""
    entry = make_entry()
    aioclient_mock.get(api_url(120.0, 30.0), status=500)

    assert await hass.config_entries.async_setup(entry.entry_id) is False
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.async_entity_ids("sensor") == []


async def test_unload_entry_cleans_up(
    hass, aioclient_mock, api_url, api_payload, make_entry
) -> None:
    entry = make_entry()
    aioclient_mock.get(api_url(120.0, 30.0), json=api_payload)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id) is True
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]
    # 卸载后实体只留下 registry 里的 restored 占位（HA 的既有行为），不能还带着数据
    for entity_id in hass.states.async_entity_ids("sensor"):
        state = hass.states.get(entity_id)
        assert state.state == "unavailable"
        assert state.attributes["restored"] is True


async def test_unload_failure_keeps_coordinator(
    hass, aioclient_mock, api_url, api_payload, make_entry
) -> None:
    """平台卸载失败时不能把 coordinator 丢掉，否则条目还活着但数据源没了。"""
    entry = make_entry()
    aioclient_mock.get(api_url(120.0, 30.0), json=api_payload)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    ):
        assert await async_unload_entry(hass, entry) is False

    assert entry.entry_id in hass.data[DOMAIN]


async def test_two_entries_are_independent(
    hass, aioclient_mock, api_url, api_payload, make_entry
) -> None:
    """多地点是这套集成的核心用法：两个条目各自打各自的坐标。"""
    home = make_entry(longitude=110.0, latitude=21.0, name="家")
    office = make_entry(longitude=116.4, latitude=39.9, name="公司")
    aioclient_mock.get(api_url(110.0, 21.0), json=api_payload)
    aioclient_mock.get(api_url(116.4, 39.9), json={**api_payload, "msg": "公司有雨"})

    # HA 在 setup 其中一个条目时会把同域名的条目一起拉起来，这里只需触发一次
    await hass.config_entries.async_setup(home.entry_id)
    await hass.async_block_till_done()
    assert office.state is ConfigEntryState.LOADED

    assert len(hass.states.async_entity_ids("sensor")) == 4
    assert hass.data[DOMAIN][home.entry_id] is not hass.data[DOMAIN][office.entry_id]

    by_name = {
        state.name: state
        for state in (
            hass.states.get(eid) for eid in hass.states.async_entity_ids("sensor")
        )
    }
    assert by_name["家 Nearby Rain"].state == "未来2小时不会降雨"
    assert by_name["公司 Nearby Rain"].state == "公司有雨"
    assert by_name["家 Nearby Rain"].attributes["longitude"] == 110.0
    assert by_name["公司 Nearby Rain"].attributes["longitude"] == 116.4


# ==========================================================================
# 选项流：预填 / 保存 / 生效
# ==========================================================================


async def test_coordinator_update_direct(
    hass, aioclient_mock, api_url, api_payload
) -> None:
    loc = {CONF_NAME: "测试", CONF_LONGITUDE: 120.0, CONF_LATITUDE: 30.0}
    coord = CnMinuteRainCoordinator(
        hass, async_get_clientsession(hass), loc, timedelta(seconds=300)
    )
    aioclient_mock.get(api_url(120.0, 30.0), json=api_payload)

    data = await coord._async_update_data()

    assert data["msg"] == "未来2小时不会降雨"
    assert data["values"] == [0.0, 0.0, 0.0, 0.0, 0.0]
    assert data["name"] == "测试"
    assert data["longitude"] == 120.0


async def test_options_flow_edit_location(
    hass, aioclient_mock, api_url, api_payload, make_entry
) -> None:
    """打开“设置”应预填已存值；保存后 options 与预填都要跟上。"""
    entry = make_entry()
    aioclient_mock.get(api_url(120.0, 30.0), json=api_payload)
    aioclient_mock.get(api_url(121.0, 31.0), json=api_payload)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
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


async def test_options_change_takes_effect_immediately(
    hass, aioclient_mock, api_url, api_payload, make_entry
) -> None:
    """回归：改完地点/间隔必须重载条目。

    以前没有注册 update listener，options 写进去了但 coordinator 还是老对象、
    老坐标、老间隔 —— 用户得重启 HA 才生效，而当时的测试只断言了 options 的值，
    所以一直绿灯。
    """
    entry = make_entry(scan_interval=5)
    aioclient_mock.get(api_url(120.0, 30.0), json=api_payload)
    aioclient_mock.get(api_url(121.0, 31.0), json=api_payload)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    old_coord = hass.data[DOMAIN][entry.entry_id]
    assert old_coord.update_interval == timedelta(minutes=5)
    assert old_coord.longitude == 120.0

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_LONGITUDE: 121.0,
            CONF_LATITUDE: 31.0,
            CONF_SCAN_INTERVAL: 10,
        },
    )
    await hass.async_block_till_done()

    new_coord = hass.data[DOMAIN][entry.entry_id]
    assert new_coord is not old_coord
    assert new_coord.update_interval == timedelta(minutes=10)
    assert new_coord.longitude == 121.0
    assert new_coord.latitude == 31.0

    # 实体也吃到新数据（attributes 里的坐标跟着变）
    assert {
        state.attributes["longitude"]
        for state in (
            hass.states.get(eid) for eid in hass.states.async_entity_ids("sensor")
        )
        if "longitude" in state.attributes
    } == {121.0}


async def test_options_flow_shows_stored_not_ha_location(
    hass, aioclient_mock, api_url, api_payload, make_entry
) -> None:
    """回归：条目里存的是用户真实地点（非 HA 坐标），打开“设置”必须回显真实值。"""
    entry = make_entry(longitude=110.0, latitude=21.0)
    aioclient_mock.get(api_url(110.0, 21.0), json=api_payload)
    aioclient_mock.get(api_url(120.0, 30.0), json=api_payload)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    suggested = _suggested_values_from_schema(result["data_schema"])
    assert suggested[CONF_LATITUDE] == 21.0
    assert suggested[CONF_LONGITUDE] == 110.0


async def test_legacy_entry_keeps_location(
    hass, aioclient_mock, api_url, api_payload, make_entry
) -> None:
    """升级前的老条目把坐标存在 data 里：既要能跑起来，选项流也不能把它冲掉。"""
    entry = make_entry(longitude=-70.5, latitude=-33.25, name="老条目", source="data")
    aioclient_mock.get(api_url(-70.5, -33.25), json=api_payload)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coord = hass.data[DOMAIN][entry.entry_id]
    assert coord.longitude == -70.5
    assert coord.latitude == -33.25
    assert coord.location_name == "老条目"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    suggested = _suggested_values_from_schema(result["data_schema"])
    # 只读 options 的话这里会回退成 HA 实例坐标，用户一保存就把地点改了
    assert suggested[CONF_LATITUDE] == -33.25
    assert suggested[CONF_LONGITUDE] == -70.5
