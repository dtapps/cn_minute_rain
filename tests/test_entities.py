"""传感器实体测试：属性、图标、可用性、unique_id 稳定性、残留清理。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.cn_minute_rain.const import DOMAIN
from custom_components.cn_minute_rain.coordinator import CnMinuteRainCoordinator
from custom_components.cn_minute_rain.sensor import (
    SENSOR_DESCRIPTIONS,
    CnMinuteRainSensor,
)

RAIN_NOW = {
    "msg": "即将下雨",
    "values": [1, 2, 3, 0, 0],
    "time": "20240101000000",
}
RAIN_LATER = {
    "msg": "2小时后有雨",
    "values": [0, 0, 1, 2, 0],
    "time": "20240101000000",
}
NO_RAIN = {
    "msg": "未来2小时不会降雨",
    "values": [0, 0, 0, 0, 0],
    "time": "20240101000000",
}


# --------------------------------------------------------------------------
# 数据都没取到时的兜底（coordinator.data is None）
# --------------------------------------------------------------------------


def test_properties_fall_back_when_coordinator_has_no_data(hass, make_entry) -> None:
    entry = make_entry()
    coord = CnMinuteRainCoordinator(
        hass,
        object(),  # 不联网，只要一个占位 session
        {"name": "测试", "longitude": 120.0, "latitude": 30.0},
        timedelta(minutes=5),
    )
    assert coord.data is None

    nearby = CnMinuteRainSensor(coord, entry, SENSOR_DESCRIPTIONS[0])
    tip = CnMinuteRainSensor(coord, entry, SENSOR_DESCRIPTIONS[1])

    assert nearby.native_value is None
    assert tip.native_value is None
    assert nearby.extra_state_attributes == {}
    assert tip.extra_state_attributes == {}
    assert nearby.icon == "mdi:weather-pouring"
    assert tip.icon == "mdi:weather-rainy"


# --------------------------------------------------------------------------
# 属性与图标
# --------------------------------------------------------------------------


async def test_nearby_attributes(hass, aioclient_mock, api_url, make_entry) -> None:
    entry = make_entry(longitude=110.0, latitude=21.0, name="家")
    aioclient_mock.get(api_url(110.0, 21.0), json=RAIN_NOW)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    nearby = next(
        hass.states.get(eid)
        for eid in hass.states.async_entity_ids("sensor")
        if hass.states.get(eid).attributes["values"] is not None
        and "latitude" in hass.states.get(eid).attributes
    )

    assert nearby.state == "即将下雨"
    assert nearby.attributes["values"] == [1.0, 2.0, 3.0, 0.0, 0.0]
    assert nearby.attributes["time"] == "20240101000000"
    assert nearby.attributes["longitude"] == 110.0
    assert nearby.attributes["latitude"] == 21.0
    assert nearby.attributes["icon"] == "mdi:weather-pouring"


@pytest.mark.parametrize(
    ("payload", "expected_state_fragment", "expected_icon"),
    [
        pytest.param(RAIN_NOW, "正在下雨", "mdi:weather-pouring", id="raining-now"),
        pytest.param(
            RAIN_LATER, "分钟后开始下雨", "mdi:weather-rainy", id="rain-later"
        ),
        pytest.param(NO_RAIN, "无雨", "mdi:weather-sunny", id="no-rain"),
    ],
)
async def test_tip_state_and_icon(
    hass,
    aioclient_mock,
    api_url,
    make_entry,
    payload,
    expected_state_fragment,
    expected_icon,
) -> None:
    entry = make_entry()
    aioclient_mock.get(api_url(120.0, 30.0), json=payload)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    tip_state = next(
        hass.states.get(eid)
        for eid in hass.states.async_entity_ids("sensor")
        if "minutes_to_rain" in hass.states.get(eid).attributes
    )

    assert expected_state_fragment in tip_state.state
    assert tip_state.attributes["icon"] == expected_icon


async def test_tip_attributes(hass, aioclient_mock, api_url, make_entry) -> None:
    entry = make_entry()
    # n=5 -> step 24；第一个有雨的索引是 2 -> 48 分钟后开始
    aioclient_mock.get(api_url(120.0, 30.0), json=RAIN_LATER)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    tip_state = next(
        hass.states.get(eid)
        for eid in hass.states.async_entity_ids("sensor")
        if "minutes_to_rain" in hass.states.get(eid).attributes
    )

    assert tip_state.attributes["minutes_to_rain"] == 48
    assert tip_state.attributes["rain_minutes"] == 48


# --------------------------------------------------------------------------
# 可用性：接口挂了要 unavailable，而不是留旧值假装没事
# --------------------------------------------------------------------------


async def test_entities_become_unavailable_after_refresh_failure(
    hass, aioclient_mock, api_url, make_entry
) -> None:
    entry = make_entry()
    aioclient_mock.get(api_url(120.0, 30.0), json=NO_RAIN)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("sensor")
    assert len(entity_ids) == 2
    assert all(hass.states.get(eid).state != "unavailable" for eid in entity_ids)

    aioclient_mock.clear_requests()
    aioclient_mock.get(api_url(120.0, 30.0), status=503)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await hass.async_block_till_done()

    assert all(hass.states.get(eid).state == "unavailable" for eid in entity_ids)


# --------------------------------------------------------------------------
# 实体身份：unique_id 只认 entry_id + key，改名改坐标不能换新实体
# --------------------------------------------------------------------------


async def test_unique_ids_survive_options_change(
    hass, aioclient_mock, api_url, make_entry
) -> None:
    entry = make_entry(name="旧名字")
    aioclient_mock.get(api_url(120.0, 30.0), json=NO_RAIN)
    aioclient_mock.get(api_url(121.0, 31.0), json=NO_RAIN)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    before = {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(reg, entry.entry_id)
    }
    assert set(before) == {f"{entry.entry_id}_nearby", f"{entry.entry_id}_tip"}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"longitude": 121.0, "latitude": 31.0, "scan_interval": 10},
    )
    await hass.async_block_till_done()

    after = {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(reg, entry.entry_id)
    }
    # 改坐标/改名后 unique_id 与 entity_id 都不许变，否则 HA 里会攒出一堆重复实体
    assert after == before


async def test_stale_entity_is_removed_on_setup(
    hass, aioclient_mock, api_url, make_entry
) -> None:
    """历史上被删掉的传感器残留在注册表里时，setup 要顺手清掉。"""
    entry = make_entry()
    reg = er.async_get(hass)
    ghost = reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_ghost",
        config_entry=entry,
        suggested_object_id="ghost",
    )
    assert reg.async_get(ghost.entity_id) is not None

    aioclient_mock.get(api_url(120.0, 30.0), json=NO_RAIN)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert reg.async_get(ghost.entity_id) is None
    assert len(er.async_entries_for_config_entry(reg, entry.entry_id)) == 2
