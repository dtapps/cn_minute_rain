"""Config flow for cn_minute_rain."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    """经纬度 / 更新间隔表单（字段用 NumberSelector，便于输入浮点坐标）。"""
    return vol.Schema(
        {
            vol.Required(CONF_LATITUDE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-90, max=90, step="any", mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_LONGITUDE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-180, max=180, step="any", mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_SCAN_INTERVAL): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=1440, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


class CnMinuteRainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """配置流：每个集成条目对应一个地点。想加多个地点就重复添加本集成。"""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """初次添加：显示经纬度与更新间隔（多个地点可重复添加）。"""
        if user_input is not None:
            longitude = float(user_input[CONF_LONGITUDE])
            latitude = float(user_input[CONF_LATITUDE])
            scan_interval = int(user_input[CONF_SCAN_INTERVAL])
            options = {
                CONF_NAME: _format_name(latitude, longitude),
                CONF_LONGITUDE: longitude,
                CONF_LATITUDE: latitude,
                CONF_SCAN_INTERVAL: scan_interval,
            }
            # 地点信息统一放在 options（HA 惯例，参考能跑的项目），data 留空，
            # 避免 data / options 双份导致读取不一致、预填出错。
            return self.async_create_entry(
                title=options[CONF_NAME], data={}, options=options
            )

        # 经纬度**不**预填 HA 实例坐标（旧版本把 HA 坐标当默认预填，用户直接保存后
        # 条目里就存了 HA 坐标，导致“修改地点”永远回显 HA 坐标）。这里只给更新间隔
        # 一个默认值，经纬度留空，强制用户显式输入要追踪的地点。
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _loc_schema(self.hass),
                {CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_MINUTES},
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """HA 以同步方式调用此方法，不要写成 async（否则返回的是未 await 的协程，点“设置”会 500）。"""
        return CnMinuteRainOptionsFlowHandler()


class CnMinuteRainOptionsFlowHandler(config_entries.OptionsFlow):
    """选项流：修改本条目对应的单个地点与更新间隔（“修改地点”）。

    读取 self.config_entry.options 的已存值，通过 add_suggested_values_to_schema
    注入字段的 suggested_value，前端即可正确预填。这是 HA 官方推荐的 options 预填写法。
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            longitude = float(user_input[CONF_LONGITUDE])
            latitude = float(user_input[CONF_LATITUDE])
            scan_interval = int(user_input[CONF_SCAN_INTERVAL])
            # OptionsFlow.async_create_entry 的 data 参数即写入 entry.options。
            return self.async_create_entry(
                title=_format_name(latitude, longitude),
                data={
                    CONF_NAME: _format_name(latitude, longitude),
                    CONF_LONGITUDE: longitude,
                    CONF_LATITUDE: latitude,
                    CONF_SCAN_INTERVAL: scan_interval,
                },
            )

        opts = self.config_entry.options
        suggested = {
            CONF_LATITUDE: float(
                opts.get(CONF_LATITUDE, self.hass.config.latitude or 39.9)
            ),
            CONF_LONGITUDE: float(
                opts.get(CONF_LONGITUDE, self.hass.config.longitude or 120.0)
            ),
            CONF_SCAN_INTERVAL: int(
                opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
            ),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _loc_schema(self.hass), suggested
            ),
        )
