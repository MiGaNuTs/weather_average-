# Weather Average

A Home Assistant custom component that aggregates multiple `weather.*` entities into a single, more reliable weather entity.

## How it works

Instead of blindly averaging values, Weather Average uses robust statistical methods for each type of data:

| Data | Method | Why |
|---|---|---|
| Temperature, humidity, pressure, wind speed, etc. | **Median** | Resistant to outliers — one bad source won't skew the result |
| Wind bearing | **Circular average** | Angles can't be medianed naively (350° and 10° should give 0°, not 180°) |
| Condition (sunny, cloudy, rainy…) | **Majority vote** | Most frequent condition wins; ties broken in favor of the most severe |
| Dew point | **Calculated** | Derived from median temp + median humidity via Magnus formula |
| Apparent temperature | **Calculated** | Derived from median temp + calculated dew point via Steadman formula |

Forecast aggregation (daily and hourly) uses the same methods, aligning slots by date/hour across all sources.

## Features

- Automatically discovers all available `weather.*` entities in your HA instance
- Median aggregation for all numerical values — robust against outliers
- Circular average for wind bearing
- Majority vote for weather condition (conservative tiebreaker — most severe wins)
- Daily and hourly forecast aggregation
- Dew point and apparent (feels-like) temperature calculated from aggregated values
- Skips unavailable sources gracefully — excluded from aggregation, no crash
- Reactive: updates instantly when any source changes state
- Add/remove sources at any time via the UI (Options flow)
- Compatible with HACS

## Installation

### Via HACS (recommended)

1. In HACS, go to **Integrations → Custom repositories**
2. Add this repository URL, category: **Integration**
3. Install **Weather Average**
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/weather_average/` folder into your HA `/config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration → Weather Average**
2. Give it a name and select at least 2 source `weather.*` entities
3. A new `weather.*` entity appears, ready to use in dashboards and automations

To add or remove sources later: **Settings → Devices & Services → Weather Average → Configure**

## Tips

- More sources = more stable results. 4–6 sources is a good sweet spot.
- Mix sources from different providers and different underlying weather models for best results (e.g. Met.no + Météo-France + Open-Meteo + OpenWeatherMap + Tomorrow.io + AccuWeather).
- The median approach means one bad source won't ruin your data — but it won't help either. Prefer quality sources over quantity.
- The condition tiebreaker favors the most severe condition (e.g. rainy beats partlycloudy in a tie) — better to bring an umbrella you didn't need than the reverse.

## Requirements

- Home Assistant 2024.1 or newer
- At least 2 `weather.*` source entities

## License

MIT
