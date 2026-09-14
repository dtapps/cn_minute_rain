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
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)


def _loc_schema(
    hass,
    scan_interval_default: int = DEFAULT_SCAN_INTERVAL_SECONDS,
) -> vol.Schema:
    """经纬度默认取当前 HA 实例所在的经纬度；附带“更新间隔”输入。"""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Required(
                CONF_LONGITUDE, default=hass.config.longitude
            ): vol.Coerce(float),
            vol.Required(
                CONF_LATITUDE, default=hass.config.latitude
            ): vol.Coerce(float),
            vol.Required(
                CONF_SCAN_INTERVAL, default=scan_interval_default
            ): vol.Coerce(int),
        }
    )


class CnMinuteRainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """配置流：每个集成条目对应一个地点。想加多个地点就重复添加本集成。"""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=_loc_schema(self.hass),
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
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={
                    **self._entry.data,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                },
            )
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="init",
            data_schema=_loc_schema(
                self.hass,
                scan_interval_default=self._entry.data.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
                ),
            ),
        )
