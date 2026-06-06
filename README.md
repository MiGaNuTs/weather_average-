# Weather Average

A Home Assistant custom component that aggregates multiple `weather.*` entities into a single averaged weather entity.

## Features

- Automatically discovers all available `weather.*` entities in your HA instance
- Averages numerical values: temperature, humidity, pressure, wind speed
- Skips unavailable sources gracefully (no crash, just excluded from average)
- Reactive: updates instantly when any source changes state
- Add/remove sources at any time via the UI (Options flow)

## Not yet implemented (roadmap)

- `condition` aggregation (majority vote)
- `wind_bearing` (circular average)
- `forecast` aggregation (daily/hourly)
- Per-source weighting

## Installation

### Via HACS (recommended)

Add this repository as a custom repository in HACS, then install **Weather Average**.

### Manual

1. Copy the `custom_components/weather_average/` folder into your HA `/config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration → Weather Average**.
4. Give it a name and select the source entities to average.

## Usage

Once configured, a new `weather.*` entity appears in HA. Use it anywhere you would use a standard weather entity (dashboards, automations, etc.).

To add or remove sources later: **Settings → Devices & Services → Weather Average → Configure**.

## Requirements

- Home Assistant 2024.1 or newer
- At least 2 `weather.*` source entities

## License

MIT
