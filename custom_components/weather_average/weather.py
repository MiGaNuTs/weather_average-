"""Weather Average entity."""
from __future__ import annotations

import logging
import math
import statistics
from datetime import timedelta

from homeassistant.components.weather import WeatherEntity, Forecast, WeatherEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

FORECAST_DAILY_INTERVAL = timedelta(minutes=25)
FORECAST_HOURLY_INTERVAL = timedelta(minutes=2)

CONDITION_PRIORITY = [
    "sunny",
    "clear-night",
    "partlycloudy",
    "windy-variant",
    "windy",
    "fog",
    "cloudy",
    "hail",
    "snowy",
    "snowy-rainy",
    "rainy",
    "pouring",
    "lightning",
    "lightning-rainy",
    "exceptional",
]


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
    _attr_native_temperature_unit = "°C"
    _attr_native_pressure_unit = "hPa"
    _attr_native_wind_speed_unit = "km/h"
    _attr_native_wind_gust_speed_unit = "km/h"
    _attr_native_visibility_unit = "km"
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, sources: list[str]):
        self.hass = hass
        self._entry = entry
        self._sources = sources
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._attr_condition = None
        self._attr_native_temperature = None
        self._attr_humidity = None
        self._attr_native_pressure = None
        self._attr_native_wind_speed = None
        self._attr_native_wind_gust_speed = None
        self._attr_wind_bearing = None
        self._attr_cloud_coverage = None
        self._attr_native_visibility = None
        self._attr_native_dew_point = None
        self._attr_native_apparent_temperature = None
        self._daily_forecast: list[Forecast] = []
        self._hourly_forecast: list[Forecast] = []
        self._update()

    async def async_added_to_hass(self) -> None:
        """Start listening to source entity state changes and schedule forecast refresh."""
        # Current values: reactive on state changes
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._sources,
                self._handle_source_update,
            )
        )
        # Daily forecast: poll every 25 minutes
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_forecast_update,
                FORECAST_DAILY_INTERVAL,
            )
        )
        # Hourly forecast: poll every 2 minutes (for testing)
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_hourly_forecast_update,
                FORECAST_HOURLY_INTERVAL,
            )
        )
        # Initial forecast fetch
        await self._async_update_forecasts()
        await self._async_update_hourly_forecasts()

    @callback
    def _handle_source_update(self, event) -> None:
        """Called whenever a source weather entity changes state."""
        self._update()
        self.async_write_ha_state()

    async def _handle_forecast_update(self, _now=None) -> None:
        """Called by the daily time interval tracker."""
        await self._async_update_forecasts()
        self.async_write_ha_state()

    async def _handle_hourly_forecast_update(self, _now=None) -> None:
        """Called by the hourly time interval tracker."""
        await self._async_update_hourly_forecasts()
        self.async_write_ha_state()

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _median(values: list) -> float | None:
        """Compute median ignoring None values."""
        clean = [v for v in values if v is not None]
        if not clean:
            return None
        return round(statistics.median(clean), 1)

    @staticmethod
    def _circular_avg(bearings: list) -> float | None:
        """Compute circular average of angles in degrees, ignoring None values."""
        clean = [b for b in bearings if b is not None]
        if not clean:
            return None
        sin_avg = sum(math.sin(math.radians(b)) for b in clean) / len(clean)
        cos_avg = sum(math.cos(math.radians(b)) for b in clean) / len(clean)
        return round(math.degrees(math.atan2(sin_avg, cos_avg)) % 360, 1)

    @staticmethod
    def _majority_vote(conditions: list[str]) -> str | None:
        """Return the most frequent condition, using CONDITION_PRIORITY as tiebreaker."""
        clean = [c for c in conditions if c is not None]
        if not clean:
            return None
        counts: dict[str, int] = {}
        for c in clean:
            counts[c] = counts.get(c, 0) + 1
        max_count = max(counts.values())
        candidates = [c for c, n in counts.items() if n == max_count]
        if len(candidates) == 1:
            return candidates[0]
        for condition in CONDITION_PRIORITY:
            if condition in candidates:
                return condition
        return candidates[0]

    @staticmethod
    def _compute_dew_point(temp: float | None, humidity: float | None) -> float | None:
        """Compute dew point from temperature and humidity using Magnus formula."""
        if temp is None or humidity is None or humidity <= 0:
            return None
        gamma = math.log(humidity / 100) + (7.5 * temp) / (237.7 + temp)
        return round(237.7 * gamma / (7.5 - gamma), 1)

    @staticmethod
    def _compute_apparent_temp(temp: float | None, dew_point: float | None) -> float | None:
        """Compute apparent temperature (Steadman) from temp and dew point."""
        if temp is None or dew_point is None:
            return None
        e = 6.11 * (10 ** ((7.5 * dew_point) / (237.7 + dew_point)))
        return round(temp + 0.5555 * (e - 10), 1)

    # ── Current values ────────────────────────────────────────────────────────

    def _update(self) -> None:
        """Recompute current values from all available sources."""
        temps, humidities, pressures = [], [], []
        wind_speeds, wind_gust_speeds, wind_bearings = [], [], []
        cloud_coverages, visibilities, conditions = [], [], []
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
            wind_gust_speeds.append(attrs.get("wind_gust_speed"))
            cloud_coverages.append(attrs.get("cloud_coverage"))
            visibilities.append(attrs.get("visibility"))
            bearing = attrs.get("wind_bearing")
            wind_bearings.append(float(bearing) if bearing is not None else None)
            conditions.append(state.state if state.state in CONDITION_PRIORITY else None)

        if available_count == 0:
            _LOGGER.warning("No weather sources available, setting state to unavailable.")
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_temperature = self._median(temps)
        self._attr_humidity = self._median(humidities)
        self._attr_native_pressure = self._median(pressures)
        self._attr_native_wind_speed = self._median(wind_speeds)
        self._attr_native_wind_gust_speed = self._median(wind_gust_speeds)
        self._attr_wind_bearing = self._circular_avg(wind_bearings)
        self._attr_cloud_coverage = self._median(cloud_coverages)
        self._attr_native_visibility = self._median(visibilities)
        self._attr_condition = self._majority_vote(conditions)
        self._attr_native_dew_point = self._compute_dew_point(
            self._attr_native_temperature, self._attr_humidity
        )
        self._attr_native_apparent_temperature = self._compute_apparent_temp(
            self._attr_native_temperature, self._attr_native_dew_point
        )

        _LOGGER.debug(
            "Current updated: temp=%s, apparent=%s, condition=%s (%d/%d sources)",
            self._attr_native_temperature,
            self._attr_native_apparent_temperature,
            self._attr_condition,
            available_count,
            len(self._sources),
        )

    # ── Daily forecast ────────────────────────────────────────────────────────

    async def _async_update_forecasts(self) -> None:
        """Fetch and aggregate daily forecasts from all sources."""
        # Collect forecasts per source
        all_forecasts: list[list[dict]] = []

        for entity_id in self._sources:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown"):
                continue
            try:
                response = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": entity_id, "type": "daily"},
                    blocking=True,
                    return_response=True,
                )
                forecasts = response.get(entity_id, {}).get("forecast", [])
                if forecasts:
                    all_forecasts.append(forecasts)
            except Exception as err:
                _LOGGER.debug("Could not get daily forecast from %s: %s", entity_id, err)

        if not all_forecasts:
            _LOGGER.warning("No daily forecasts available from any source.")
            self._daily_forecast = []
            return

        # Align slots by date (YYYY-MM-DD) and aggregate
        slots: dict[str, dict[str, list]] = {}

        for source_forecasts in all_forecasts:
            for slot in source_forecasts:
                # Normalize date key — datetime can be "2025-06-07T00:00:00+00:00" or just a date
                raw_date = slot.get("datetime", "")
                date_key = raw_date[:10]  # Keep only YYYY-MM-DD
                if not date_key:
                    continue
                if date_key not in slots:
                    slots[date_key] = {
                        "templow": [],
                        "temperature": [],
                        "humidity": [],
                        "precipitation": [],
                        "precipitation_probability": [],
                        "wind_speed": [],
                        "wind_bearing": [],
                        "condition": [],
                    }
                s = slots[date_key]
                s["templow"].append(slot.get("templow"))
                s["temperature"].append(slot.get("temperature"))
                s["humidity"].append(slot.get("humidity"))
                s["precipitation"].append(slot.get("precipitation"))
                s["precipitation_probability"].append(slot.get("precipitation_probability"))
                s["wind_speed"].append(slot.get("wind_speed"))
                bearing = slot.get("wind_bearing")
                s["wind_bearing"].append(float(bearing) if bearing is not None else None)
                cond = slot.get("condition")
                s["condition"].append(cond if cond in CONDITION_PRIORITY else None)

        # Build aggregated forecast list, sorted by date
        result: list[Forecast] = []
        for date_key in sorted(slots.keys()):
            s = slots[date_key]
            result.append(
                Forecast(
                    datetime=f"{date_key}T00:00:00+00:00",
                    condition=self._majority_vote(s["condition"]),
                    native_temperature=self._median(s["temperature"]),
                    native_templow=self._median(s["templow"]),
                    humidity=self._median(s["humidity"]),
                    native_precipitation=self._median(s["precipitation"]),
                    precipitation_probability=self._median(s["precipitation_probability"]),
                    native_wind_speed=self._median(s["wind_speed"]),
                    wind_bearing=self._circular_avg(s["wind_bearing"]),
                )
            )

        self._daily_forecast = result
        _LOGGER.debug("Daily forecast updated: %d slots aggregated.", len(result))

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the aggregated daily forecast."""
        return self._daily_forecast or None

    async def _async_update_hourly_forecasts(self) -> None:
        """Fetch and aggregate hourly forecasts from all sources."""
        all_forecasts: list[list[dict]] = []

        for entity_id in self._sources:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown"):
                continue
            try:
                response = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": entity_id, "type": "hourly"},
                    blocking=True,
                    return_response=True,
                )
                forecasts = response.get(entity_id, {}).get("forecast", [])
                if forecasts:
                    all_forecasts.append(forecasts)
            except Exception as err:
                _LOGGER.debug("Could not get hourly forecast from %s: %s", entity_id, err)

        if not all_forecasts:
            _LOGGER.warning("No hourly forecasts available from any source.")
            self._hourly_forecast = []
            return

        # Align slots by hour (YYYY-MM-DDTHH) and aggregate
        slots: dict[str, dict[str, list]] = {}

        for source_forecasts in all_forecasts:
            for slot in source_forecasts:
                raw_dt = slot.get("datetime", "")
                hour_key = raw_dt[:13]  # Keep YYYY-MM-DDTHH
                if not hour_key:
                    continue
                if hour_key not in slots:
                    slots[hour_key] = {
                        "temperature": [],
                        "humidity": [],
                        "precipitation": [],
                        "precipitation_probability": [],
                        "wind_speed": [],
                        "wind_bearing": [],
                        "condition": [],
                    }
                s = slots[hour_key]
                s["temperature"].append(slot.get("temperature"))
                s["humidity"].append(slot.get("humidity"))
                s["precipitation"].append(slot.get("precipitation"))
                s["precipitation_probability"].append(slot.get("precipitation_probability"))
                s["wind_speed"].append(slot.get("wind_speed"))
                bearing = slot.get("wind_bearing")
                s["wind_bearing"].append(float(bearing) if bearing is not None else None)
                cond = slot.get("condition")
                s["condition"].append(cond if cond in CONDITION_PRIORITY else None)

        result: list[Forecast] = []
        for hour_key in sorted(slots.keys()):
            s = slots[hour_key]
            result.append(
                Forecast(
                    datetime=f"{hour_key}:00:00+00:00",
                    condition=self._majority_vote(s["condition"]),
                    native_temperature=self._median(s["temperature"]),
                    humidity=self._median(s["humidity"]),
                    native_precipitation=self._median(s["precipitation"]),
                    precipitation_probability=self._median(s["precipitation_probability"]),
                    native_wind_speed=self._median(s["wind_speed"]),
                    wind_bearing=self._circular_avg(s["wind_bearing"]),
                )
            )

        self._hourly_forecast = result
        _LOGGER.debug("Hourly forecast updated: %d slots aggregated.", len(result))

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the aggregated hourly forecast."""
        return self._hourly_forecast or None
