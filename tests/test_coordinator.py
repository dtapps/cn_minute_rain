"""Coordinator 测试：values 解析 + 真实请求路径（成功 / 失败 / 异常）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from aiohttp import ClientError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.cn_minute_rain import coordinator as coordinator_module
from custom_components.cn_minute_rain.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    REQUEST_TIMEOUT_SECONDS,
)
from custom_components.cn_minute_rain.coordinator import (
    CnMinuteRainCoordinator,
    parse_values,
)

# --------------------------------------------------------------------------
# parse_values：接口返回值的三种形态（None / 逗号串 / 数组）
# --------------------------------------------------------------------------


def test_parse_values_none() -> None:
    assert parse_values(None) == []


def test_parse_values_str_comma() -> None:
    assert parse_values("1,2,3") == [1.0, 2.0, 3.0]


def test_parse_values_str_with_blank_and_spaces() -> None:
    assert parse_values("1,, 2 ,") == [1.0, 2.0]


def test_parse_values_str_empty_or_blank() -> None:
    assert parse_values("") == []
    assert parse_values("  ,  , ") == []


def test_parse_values_list_mixed() -> None:
    assert parse_values([1, 2.5, "3"]) == [1.0, 2.5, 3.0]


def test_parse_values_list_skips_unconvertible_items() -> None:
    """数组里混进坏值只丢坏的那一项，不该整段报废。"""
    assert parse_values([1, "x", None, {"a": 1}, 2]) == [1.0, 2.0]


def test_parse_values_tuple() -> None:
    assert parse_values(("1", 2)) == [1.0, 2.0]


def test_parse_values_invalid_returns_empty() -> None:
    assert parse_values("a,b") == []
    assert parse_values(123) == []
    assert parse_values({"x": 1}) == []


# --------------------------------------------------------------------------
# _async_update_data：成功路径
# --------------------------------------------------------------------------


class FakeResponse:
    """够用的假响应：只要 raise_for_status 与 json 两个口子。"""

    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    async def json(self):
        return self._payload


def _make_coord(
    hass,
    *,
    session: object | None = None,
    longitude: float = 120.0,
    latitude: float = 30.0,
) -> CnMinuteRainCoordinator:
    return CnMinuteRainCoordinator(
        hass,
        async_get_clientsession(hass) if session is None else session,
        {
            CONF_NAME: "测试",
            CONF_LONGITUDE: longitude,
            CONF_LATITUDE: latitude,
        },
        timedelta(seconds=300),
    )


async def test_update_data_success(hass, aioclient_mock, api_url, api_payload) -> None:
    coord = _make_coord(hass)
    aioclient_mock.get(api_url(120.0, 30.0), json=api_payload)

    data = await coord._async_update_data()

    assert data["msg"] == "未来2小时不会降雨"
    assert data["values"] == [0.0, 0.0, 0.0, 0.0, 0.0]
    assert data["time"] == "20240101000000"
    assert data["name"] == "测试"
    assert data["longitude"] == 120.0
    assert data["latitude"] == 30.0


async def test_update_data_sends_expected_headers(hass) -> None:
    """接口不带 UA / Referer 会被拒，这两个头是被依赖的行为，别让它悄悄消失。"""

    class RecordingSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def get(self, url, headers=None, **kwargs):
            self.calls.append((url, headers or {}))
            return FakeResponse({"msg": "m", "values": [0], "time": "t"})

    session = RecordingSession()
    coord = CnMinuteRainCoordinator(
        hass,
        session,
        {CONF_NAME: "测试", CONF_LONGITUDE: 120.0, CONF_LATITUDE: 30.0},
        timedelta(seconds=300),
    )

    await coord._async_update_data()

    url, headers = session.calls[-1]
    assert url == "https://mpf.weather.com.cn/mpf_v3/webgis/minute?lon=120.0&lat=30.0"
    assert headers["User-Agent"] == "HomeAssistant/cn_minute_rain"
    assert headers["Referer"] == "https://www.weather.com.cn/"


async def test_update_data_missing_keys_fall_back(
    hass, aioclient_mock, api_url
) -> None:
    """接口字段缺失时给兜底值，别让 KeyError 冒出去。"""
    coord = _make_coord(hass)
    aioclient_mock.get(api_url(120.0, 30.0), json={"values": None})

    data = await coord._async_update_data()

    assert data["msg"] == "未知"
    assert data["values"] == []
    assert data["time"] is None


async def test_update_data_string_values(hass, aioclient_mock, api_url) -> None:
    """真实接口有时把 values 给成逗号串，走同一套解析。"""
    coord = _make_coord(hass)
    aioclient_mock.get(api_url(120.0, 30.0), json={"msg": "m", "values": "0,1.5,2"})

    data = await coord._async_update_data()

    assert data["values"] == [0.0, 1.5, 2.0]


# --------------------------------------------------------------------------
# _async_update_data：失败路径 —— 全部要变成 UpdateFailed
# （HA 靠它把实体置为 unavailable，而不是让异常直接炸穿）
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "response_kwargs",
    [
        pytest.param({"status": 500}, id="http-500"),
        pytest.param({"status": 404}, id="http-404"),
        pytest.param({"exc": ClientError("connection reset")}, id="client-error"),
        pytest.param({"text": "<html>oops</html>"}, id="not-json"),
    ],
)
async def test_update_data_wraps_errors_in_update_failed(
    hass, aioclient_mock, api_url, response_kwargs
) -> None:
    coord = _make_coord(hass)
    aioclient_mock.get(api_url(120.0, 30.0), **response_kwargs)

    with pytest.raises(UpdateFailed) as err:
        await coord._async_update_data()

    # 报错里要能看出是哪个地点挂了，否则多地点用户没法排查。
    assert "测试" in str(err.value)


async def test_update_data_wraps_timeout_in_update_failed(hass) -> None:
    """超时也必须被包成 UpdateFailed，不能裸抛。"""

    class HangingSession:
        async def get(self, *args, **kwargs):
            raise TimeoutError

    coord = _make_coord(hass, session=HangingSession())

    with pytest.raises(UpdateFailed) as err:
        await coord._async_update_data()

    assert "测试" in str(err.value)


async def test_update_data_aborts_when_request_hangs(hass, monkeypatch) -> None:
    """请求卡住时要按配置的超时切断，而不是把 HA 的事件循环吊死。"""
    import asyncio

    class SlowSession:
        async def get(self, *args, **kwargs):
            # 睡够再给一个合法响应：如果超时没生效，这次请求会“成功”，测试就会挂，
            # 而不是靠别的异常蒙混过关。
            await asyncio.sleep(0.5)
            return FakeResponse({"msg": "太晚了", "values": [0], "time": "t"})

    monkeypatch.setattr(coordinator_module, "REQUEST_TIMEOUT_SECONDS", 0.01)
    coord = _make_coord(hass, session=SlowSession())

    with pytest.raises(UpdateFailed) as err:
        await coord._async_update_data()

    assert isinstance(err.value.__cause__, TimeoutError)
    assert "测试" in str(err.value)


def test_request_timeout_is_sane() -> None:
    """超时必须是个有限的正数秒数，别被改成 0 / 无穷。"""
    assert 1 <= REQUEST_TIMEOUT_SECONDS <= 60


# --------------------------------------------------------------------------
# 构造参数归属：基类也会占 self.name，地点名必须落在 location_name
# --------------------------------------------------------------------------


def test_coordinator_stores_location_fields(hass) -> None:
    coord = _make_coord(hass, session=object(), longitude=121.5, latitude=-33.25)

    assert coord.location_name == "测试"
    assert coord.longitude == 121.5
    assert coord.latitude == -33.25
    assert coord.update_interval == timedelta(seconds=300)
    assert coord.name == "cn_minute_rain_测试"
