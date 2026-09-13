"""DataUpdateCoordinator for cn_minute_rain."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_URL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def parse_values(raw: Any) -> list[float]:
    """将 API 的 values 规整为 float 列表，兼容 字符串(逗号分隔) / 数组 两种形态。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip() != ""]
        try:
            return [float(p) for p in parts]
        except ValueError:
            return []
    if isinstance(raw, (list, tuple)):
        out: list[float] = []
        for x in raw:
            try:
                out.append(float(x))
            except (ValueError, TypeError):
                pass
        return out
    return []


class CnMinuteRainCoordinator(DataUpdateCoordinator):
    """每分钟级降水协调器，每个地点一个实例。"""

    def __init__(self, hass: HomeAssistant, session, location: dict) -> None:
        self.session = session
        # 注意：DataUpdateCoordinator 基类会把传入的 name 参数存到 self.name，
        # 因此地点名不能用 self.name，改用 self.location_name 以免被基类覆盖。
        self.location_name: str = location[CONF_NAME]
        self.longitude: float = location[CONF_LONGITUDE]
        self.latitude: float = location[CONF_LATITUDE]
        super().__init__(
            hass,
            _LOGGER,
            name=f"cn_minute_rain_{self.location_name}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        url = f"{API_URL}?lon={self.longitude}&lat={self.latitude}"
        headers = {
            "User-Agent": "HomeAssistant/cn_minute_rain",
            "Referer": "https://www.weather.com.cn/",
        }
        try:
            async with asyncio.timeout(10):
                resp = await self.session.get(url, headers=headers)
                resp.raise_for_status()
                data = await resp.json()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"获取分钟级降水失败 ({self.location_name}): {err}") from err

        return {
            "msg": data.get("msg", "未知"),
            "values": parse_values(data.get("values")),
            "time": data.get("time"),
            "name": self.location_name,
            "longitude": self.longitude,
            "latitude": self.latitude,
        }
