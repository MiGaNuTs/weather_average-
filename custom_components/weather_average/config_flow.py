"""Config flow for Weather Average."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.selector as selector

from . import DOMAIN


def _get_weather_entities(hass, exclude_entry_id=None):
    """Return all available weather entity IDs, excluding ourselves."""
    return [
        state.entity_id
        for state in hass.states.async_all("weather")
        if not (exclude_entry_id and state.entity_id == f"weather.{exclude_entry_id}")
    ]


class WeatherAverageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the first step: pick a name and select sources."""
        available = _get_weather_entities(self.hass)
        errors = {}

        if user_input is not None:
            if len(user_input.get("sources", [])) < 2:
                errors["sources"] = "min_two_sources"
            else:
                return self.async_create_entry(
                    title=user_input.get("name", "Météo moyenne"),
                    data={"sources": user_input["sources"]},
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("name", default="Météo moyenne"): str,
                    vol.Required("sources"): selector.selector(
                        {
                            "select": {
                                "options": available,
                                "multiple": True,
                            }
                        }
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry):
        """Return the options flow handler."""
        return WeatherAverageOptionsFlow(entry)


class WeatherAverageOptionsFlow(config_entries.OptionsFlow):
    """Handle options (add/remove sources after initial setup)."""

    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        available = _get_weather_entities(self.hass)
        current = self._entry.options.get(
            "sources", self._entry.data.get("sources", [])
        )
        errors = {}

        if user_input is not None:
            if len(user_input.get("sources", [])) < 2:
                errors["sources"] = "min_two_sources"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("sources", default=current): selector.selector(
                        {
                            "select": {
                                "options": available,
                                "multiple": True,
                            }
                        }
                    ),
                }
            ),
        )
