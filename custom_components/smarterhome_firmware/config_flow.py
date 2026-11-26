"""Config flow: one click to add, two options."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import CONF_INCLUDE_BETA, CONF_SKIP_COVERED, DEFAULT_INCLUDE_BETA, DEFAULT_SKIP_COVERED, DOMAIN, NAME


class SmarterHomeFirmwareConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add the integration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SmarterHomeFirmwareOptionsFlow()


class SmarterHomeFirmwareOptionsFlow(OptionsFlow):
    """Beta releases and devices that already have an update notice."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(CONF_SKIP_COVERED, default=options.get(CONF_SKIP_COVERED, DEFAULT_SKIP_COVERED)): bool,
                vol.Required(CONF_INCLUDE_BETA, default=options.get(CONF_INCLUDE_BETA, DEFAULT_INCLUDE_BETA)): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
