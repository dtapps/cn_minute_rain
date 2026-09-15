"""Config flow for cn_minute_rain."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)


def _format_name(latitude: float, longitude: float) -> str:
    """根据经纬度生成默认名称，如“降水 (21.52°N, 110.98°E)”。"""
    lat_s = f"{abs(latitude):.2f}°{'N' if latitude >= 0 else 'S'}"
    lon_s = f"{abs(longitude):.2f}°{'E' if longitude >= 0 else 'W'}"
    return f"降水 ({lat_s}, {lon_s})"


def _loc_schema(hass) -> vol.Schema:
    """基础经纬度表单（不带默认值）。

    预填值统一通过 FlowHandler.add_suggested_values_to_schema 注入到字段的
    description.suggested_value（HA 前端只认这个来预填），而不是 vol.Required 的
    default —— 后者在本版本序列化给前端时不会携带，导致打开“设置”时纬度框为空。
    """
    return vol.Schema(
        {
            vol.Required(CONF_LONGITUDE): vol.Coerce(float),
            vol.Required(CONF_LATITUDE): vol.Coerce(float),
            vol.Required(CONF_SCAN_INTERVAL): vol.Coerce(int),
        }
    )


def _suggested_values(hass, entry_data=None) -> dict:
    """构造预填值字典（首次添加，user 流）：回退到 HA 实例所在位置。"""
    if entry_data:
        return {
            CONF_LONGITUDE: entry_data.get(CONF_LONGITUDE, hass.config.longitude),
            CONF_LATITUDE: entry_data.get(CONF_LATITUDE, hass.config.latitude),
            CONF_SCAN_INTERVAL: entry_data.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
            ),
        }
    return {
        CONF_LONGITUDE: hass.config.longitude,
        CONF_LATITUDE: hass.config.latitude,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_MINUTES,
    }


def _entry_suggested(entry, hass) -> dict:
    """从已有条目读取已存储的经纬度，用于 options 流（“修改地点”）预填。

    读取优先级：entry.options > entry.data > HA 实例坐标。
    早期版本把位置写进了 entry.options，而当前条目可能只存在于 entry.data，
    因此必须两者都查，否则旧条目打开“设置”会回显成 HA 实例坐标（错误值）。
    """
    opts = entry.options or {}
    data = entry.data or {}
    return {
        CONF_LONGITUDE: opts.get(
            CONF_LONGITUDE, data.get(CONF_LONGITUDE, hass.config.longitude)
        ),
        CONF_LATITUDE: opts.get(
            CONF_LATITUDE, data.get(CONF_LATITUDE, hass.config.latitude)
        ),
        CONF_SCAN_INTERVAL: opts.get(
            CONF_SCAN_INTERVAL,
            data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        ),
    }


class CnMinuteRainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """配置流：每个集成条目对应一个地点。想加多个地点就重复添加本集成。"""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            name = _format_name(user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE])
            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME: name,
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _loc_schema(self.hass), _suggested_values(self.hass)
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """HA 以同步方式调用此方法，不要写成 async（否则返回的是未 await 的协程，点“设置”会 500）。"""
        return CnMinuteRainOptionsFlow(config_entry)


class CnMinuteRainOptionsFlow(config_entries.OptionsFlow):
    """选项流：修改本条目对应的单个地点与更新间隔。

    注意：基类 OptionsFlow 的 `config_entry` 是只读 property，且 __init__ 里不可用，
    因此这里用私有属性 `self._entry` 保存条目，避免给只读属性赋值导致 500。
    """

    def __init__(self, config_entry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            name = _format_name(user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE])
            # 同时更新 data 与 options，保证两个来源一致：
            # 旧条目可能把位置存进了 options，新条目存进 data，统一后读取才不会回显错值。
            self.hass.config_entries.async_update_entry(
                self._entry,
                title=name,
                data={
                    **self._entry.data,
                    CONF_NAME: name,
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                },
            )
            return self.async_create_entry(
                title="",
                data={
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                },
            )
        # 关键修复：打开“设置”（标题“修改地点”）时，把已存储的经纬度作为
        # suggested_value 注入表单。读取优先级 options > data > HA 实例，
        # 否则旧条目会回显成 HA 实例坐标（即“纬度不是我设置的值”）。
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _loc_schema(self.hass), _entry_suggested(self._entry, self.hass)
            ),
        )
