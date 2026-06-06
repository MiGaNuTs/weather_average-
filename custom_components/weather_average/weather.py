"""Weather Average entity."""
from __future__ import annotations

import logging
from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Weather Average entity from a config entry."""
    sources = entry.options.get("sources", entry.data.get("sources", []))
    async_add_entities([WeatherAverageEntity(hass, entry, sources)])


class WeatherAverageEntity(WeatherEntity):
    """Aggregates multiple weather entities into a single averaged entity."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, sources: list[str]):
        self.hass = hass
        self._entry = entry
        self._sources = sources
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._attr_native_temperature_unit = "°C"
        self._attr_native_pressure_unit = "hPa"
        self._attr_native_wind_speed_unit = "km/h"
        self._update()

    async def async_added_to_hass(self) -> None:
        """Start listening to source entity state changes."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._sources,
                self._handle_source_update,
            )
        )

    @callback
    def _handle_source_update(self, event) -> None:
        """Called whenever a source weather entity changes state."""
        self._update()
        self.async_write_ha_state()

    @staticmethod
    def _avg(values: list) -> float | None:
        """Compute average ignoring None values. Returns None if no valid data."""
        clean = [v for v in values if v is not None]
        if not clean:
            return None
        return round(sum(clean) / len(clean), 1)

    def _update(self) -> None:
        """Recompute averaged values from all available sources."""
        temps = []
        humidities = []
        pressures = []
        wind_speeds = []

        available_count = 0

        for entity_id in self._sources:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown"):
                _LOGGER.debug("Source %s is unavailable, skipping.", entity_id)
                continue

            available_count += 1
            attrs = state.attributes
            temps.append(attrs.get("temperature"))
            humidities.append(attrs.get("humidity"))
            pressures.append(attrs.get("pressure"))
            wind_speeds.append(attrs.get("wind_speed"))

        if available_count == 0:
            _LOGGER.warning("No weather sources available, setting state to unavailable.")
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_temperature = self._avg(temps)
        self._attr_humidity = self._avg(humidities)
        self._attr_native_pressure = self._avg(pressures)
        self._attr_native_wind_speed = self._avg(wind_speeds)

        _LOGGER.debug(
            "Updated: temp=%s, humidity=%s, pressure=%s, wind_speed=%s "
            "(%d/%d sources available)",
            self._attr_native_temperature,
            self._attr_humidity,
            self._attr_native_pressure,
            self._attr_native_wind_speed,
            available_count,
            len(self._sources),
        )
