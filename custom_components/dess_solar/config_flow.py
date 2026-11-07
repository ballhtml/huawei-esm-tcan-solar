"""Config flow for DessMonitor Solar Universal."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector

from .api import DessSolarAPI, DessSolarAuthError, DessSolarError
from .const import (
    CONF_COMPANY_KEY,
    CONF_LOCAL_MODE,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_COMPANY_KEY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOCAL_MODE_DISABLED,
    LOCAL_MODE_OPTIONS,
    UPDATE_INTERVAL_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


def _interval_options():
    return [
        {"value": str(sec), "label": label}
        for sec, label in UPDATE_INTERVAL_OPTIONS.items()
    ]


class DessSolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DessMonitor Solar Universal."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial user setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD].strip()
            company_key = user_input.get(CONF_COMPANY_KEY, DEFAULT_COMPANY_KEY).strip()
            update_interval = int(user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            api = DessSolarAPI(
                username=username,
                password=password,
                company_key=company_key,
                session=session,
            )

            try:
                await api.authenticate()
                collectors = await api.get_collectors()
                if not collectors:
                    _LOGGER.warning("Authentication succeeded, but no collectors were found")
            except DessSolarAuthError:
                errors["base"] = "invalid_auth"
            except DessSolarError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected error during login: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"DessSolar ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_COMPANY_KEY: company_key,
                        CONF_UPDATE_INTERVAL: update_interval,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=str(DEFAULT_UPDATE_INTERVAL),
                ): selector(
                    {
                        "select": {
                            "options": _interval_options(),
                            "mode": "dropdown",
                        }
                    }
                ),
                vol.Optional(
                    CONF_COMPANY_KEY,
                    default=DEFAULT_COMPANY_KEY,
                ): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow handler."""
        return DessSolarOptionsFlowHandler(config_entry)


class DessSolarOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for DessMonitor Solar Universal."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage integration options."""
        if user_input is not None:
            user_input[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL])
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            self._config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        current_local_mode = self._config_entry.options.get(
            CONF_LOCAL_MODE, LOCAL_MODE_DISABLED
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=str(current_interval),
                ): selector(
                    {
                        "select": {
                            "options": _interval_options(),
                            "mode": "dropdown",
                        }
                    }
                ),
                vol.Optional(
                    CONF_LOCAL_MODE,
                    default=current_local_mode,
                ): vol.In(LOCAL_MODE_OPTIONS),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
