"""Sensor platform for cn_minute_rain."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_registry as er
from pypinyin import lazy_pinyin

from .const import DOMAIN, PRECIP_WINDOW_MINUTES
from .coordinator import CnMinuteRainCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="nearby",
        translation_key="nearby",
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="tip",
        translation_key="tip",
        icon="mdi:weather-rainy",
    ),
)


def _compute_tip(values: list[float]) -> dict[str, Any]:
    """根据强度数组推导降雨提示（逻辑移植自原 Jinja 模板）。"""
    n = len(values)
    if n == 0 or sum(values) == 0:
        return {
            "state": "无雨",
            "rain_minutes": 0,
            "minutes_to_rain": None,
            "icon": "mdi:weather-sunny",
        }
    step = max(1, -(-PRECIP_WINDOW_MINUTES // n))  # 等价于 math.ceil(120/n)
    first = -1
    last = -1
    for i, v in enumerate(values):
        if v > 0:
            if first == -1:
                first = i
            last = i
    if first == 0:
        return {
            "state": f"🌧️ 正在下雨，预计持续约 {(last - first + 1) * step} 分钟",
            "rain_minutes": (last - first + 1) * step,
            "minutes_to_rain": 0,
            "icon": "mdi:weather-pouring",
        }
    return {
        "state": f"⏳ 约 {first * step} 分钟后开始下雨",
        "rain_minutes": (last - first + 1) * step,
        "minutes_to_rain": first * step,
        "icon": "mdi:weather-rainy",
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cn_minute_rain sensors from a config entry (每条目一个地点)."""
    coord: CnMinuteRainCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    current_ids: list[str] = []
    for description in SENSOR_DESCRIPTIONS:
        sensor = CnMinuteRainSensor(coord, entry, description)
        entities.append(sensor)
        current_ids.append(sensor.unique_id)

    # 清理已被删除地点的残留实体
    reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(reg, entry.entry_id):
        if ent.domain == "sensor" and ent.unique_id not in current_ids:
            reg.async_remove(ent.entity_id)

    async_add_entities(entities)


class CnMinuteRainSensor(CoordinatorEntity, SensorEntity):
    """分钟级降水传感器（临近降雨 / 降雨提示）。"""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coord: CnMinuteRainCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coord)
        self.entity_description = description
        self._attr_unique_id = (
            f"{entry.entry_id}_{coord.location_name}_{description.key}"
        )
        # 实体 ID 形如 sensor.cn_minute_rain_<地点拼音>_<nearby|tip>：
        # 带集成名便于识别，地点拼音保证中文也能生成可读、不撞车的 ASCII ID。
        loc_slug = "_".join(lazy_pinyin(coord.location_name))
        self._attr_suggested_object_id = f"cn_minute_rain_{loc_slug}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{coord.location_name}")},
            name=coord.location_name,
            manufacturer="中国天气网",
            model="分钟级降水预报",
        )

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        if self.entity_description.key == "nearby":
            return self.coordinator.data["msg"]
        return _compute_tip(self.coordinator.data["values"])["state"]

    @property
    def icon(self) -> str:
        if self.coordinator.data is None:
            return self.entity_description.icon
        if self.entity_description.key == "tip":
            return _compute_tip(self.coordinator.data["values"])["icon"]
        return self.entity_description.icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}
        data = self.coordinator.data
        if self.entity_description.key == "nearby":
            return {
                "values": data["values"],
                "time": data["time"],
                "longitude": data["longitude"],
                "latitude": data["latitude"],
            }
        tip = _compute_tip(data["values"])
        return {
            "minutes_to_rain": tip["minutes_to_rain"],
            "rain_minutes": tip["rain_minutes"],
        }
