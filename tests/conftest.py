"""Shared pytest fixtures and configuration for the test suite."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from yarl import URL

# Make the project root importable so tests can `import custom_components...`.
sys.path.append(str(Path(__file__).parent.parent))

from custom_components.cn_minute_rain.const import (
    API_URL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the local custom_components directory in every test."""
    yield


@pytest.fixture
def api_url() -> Callable[[float, float], str]:
    """按经纬度拼出接口的期望 URL（与 code 里 f-string 的拼法一致）。"""

    def _build(longitude: float, latitude: float) -> str:
        return str(URL(API_URL).with_query(lon=longitude, lat=latitude))

    return _build


@pytest.fixture
def api_payload() -> dict[str, Any]:
    """无雨场景的接口响应；每个测试拿到独立副本，避免互相污染。"""
    return {
        "msg": "未来2小时不会降雨",
        "values": [0, 0, 0, 0, 0],
        "time": "20240101000000",
    }


@pytest.fixture
def make_entry(hass) -> Callable[..., MockConfigEntry]:
    """造一个已挂到 hass 上的配置条目。

    source="options" 是新格式（地点存 options）；
    source="data" 复刻升级前的老条目（地点存 data），用来守住迁移路径。
    """

    def _build(
        *,
        longitude: float = 120.0,
        latitude: float = 30.0,
        scan_interval: int = 5,
        name: str = "测试",
        source: str = "options",
    ) -> MockConfigEntry:
        payload = {
            CONF_NAME: name,
            CONF_LONGITUDE: longitude,
            CONF_LATITUDE: latitude,
            CONF_SCAN_INTERVAL: scan_interval,
        }
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={} if source == "options" else payload,
            options=payload if source == "options" else {},
            version=1,
        )
        entry.add_to_hass(hass)
        return entry

    return _build
