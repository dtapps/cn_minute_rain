"""Config flow for cn_minute_rain."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_LATITUDE, CONF_LONGITUDE, CONF_LOCATIONS, CONF_NAME, DOMAIN

def _loc_schema(hass) -> vol.Schema:
    """经纬度默认取当前 HA 实例所在的经纬度。"""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_LONGITUDE, default=hass.config.longitude): vol.Coerce(
                float
            ),
            vol.Required(CONF_LATITUDE, default=hass.config.latitude): vol.Coerce(
                float
            ),
        }
    )


ADD_SCHEMA = vol.Schema(
    {
        vol.Required("add_another", default=False): bool,
    }
)

OPT_INIT_SCHEMA = vol.Schema(
    {
        vol.Required("action", default="keep"): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value="keep", label="keep"),
                    SelectOptionDict(value="edit", label="edit"),
                ],
                mode="dropdown",
            )
        ),
    }
)


class CnMinuteRainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """多地点配置流：可一次性添加多个地点。"""

    VERSION = 1

    def __init__(self) -> None:
        self._locations: list[dict] = []

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._locations.append(
                {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                }
            )
            return await self.async_step_add_another()
        return self.async_show_form(step_id="user", data_schema=_loc_schema(self.hass))

    async def async_step_add_another(self, user_input=None) -> FlowResult:
        if user_input is not None:
            if user_input["add_another"]:
                return await self.async_step_user()
            if not self._locations:
                return await self.async_step_user()
            return self._create_entry()
        return self.async_show_form(step_id="add_another", data_schema=ADD_SCHEMA)

    def _create_entry(self) -> FlowResult:
        title = self._locations[0][CONF_NAME]
        if len(self._locations) > 1:
            title += f" 等 {len(self._locations)} 个地点"
        return self.async_create_entry(
            title=title,
            data={CONF_LOCATIONS: self._locations},
        )

    @staticmethod
    async def async_get_options_flow(config_entry):
        return CnMinuteRainOptionsFlow(config_entry)


class CnMinuteRainOptionsFlow(config_entries.OptionsFlow):
    """选项流：重新设置地点列表。"""

    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry
        self._locations: list[dict] = list(config_entry.data.get(CONF_LOCATIONS, []))

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            if user_input["action"] == "edit":
                self._locations = []
                return await self.async_step_user()
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", data_schema=OPT_INIT_SCHEMA)

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._locations.append(
                {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                }
            )
            return await self.async_step_add_another()
        return self.async_show_form(step_id="user", data_schema=_loc_schema(self.hass))

    async def async_step_add_another(self, user_input=None) -> FlowResult:
        if user_input is not None:
            if user_input["add_another"]:
                return await self.async_step_user()
            if not self._locations:
                return await self.async_step_user()
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_LOCATIONS: self._locations},
            )
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="add_another", data_schema=ADD_SCHEMA)
