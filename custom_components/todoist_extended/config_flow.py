"""Config and options flow for the Todoist Extended integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TodoistApiClient, TodoistApiError, TodoistAuthError
from .const import (
    CONF_CREATE_PER_TASK_SENSORS,
    CONF_CREATE_PRIORITY_LISTS,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_CREATE_PER_TASK_SENSORS,
    DEFAULT_CREATE_PRIORITY_LISTS,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)


class TodoistExtendedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect the API token and validate it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = TodoistApiClient(user_input[CONF_TOKEN], session)
            try:
                await client.async_get_projects()
            except TodoistAuthError:
                errors["base"] = "invalid_auth"
            except TodoistApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"todoist_extended_{user_input[CONF_TOKEN][:8]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_TOKEN: user_input[CONF_TOKEN]},
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                        CONF_CREATE_PER_TASK_SENSORS: user_input.get(
                            CONF_CREATE_PER_TASK_SENSORS,
                            DEFAULT_CREATE_PER_TASK_SENSORS,
                        ),
                        CONF_CREATE_PRIORITY_LISTS: user_input.get(
                            CONF_CREATE_PRIORITY_LISTS,
                            DEFAULT_CREATE_PRIORITY_LISTS,
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_CREATE_PER_TASK_SENSORS,
                    default=DEFAULT_CREATE_PER_TASK_SENSORS,
                ): bool,
                vol.Optional(
                    CONF_CREATE_PRIORITY_LISTS,
                    default=DEFAULT_CREATE_PRIORITY_LISTS,
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "TodoistExtendedOptionsFlow":
        """Return the options flow."""
        return TodoistExtendedOptionsFlow()


class TodoistExtendedOptionsFlow(config_entries.OptionsFlow):
    """Handle updating the scan interval and per-task-sensor toggle."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_CREATE_PER_TASK_SENSORS,
                    default=opts.get(
                        CONF_CREATE_PER_TASK_SENSORS,
                        DEFAULT_CREATE_PER_TASK_SENSORS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_CREATE_PRIORITY_LISTS,
                    default=opts.get(
                        CONF_CREATE_PRIORITY_LISTS,
                        DEFAULT_CREATE_PRIORITY_LISTS,
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
