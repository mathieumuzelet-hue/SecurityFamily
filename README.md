# Shelter Finder

[![Tests](https://github.com/mathieumuzelet-hue/SecurityFamily/actions/workflows/tests.yml/badge.svg)](https://github.com/mathieumuzelet-hue/SecurityFamily/actions/workflows/tests.yml)
[![HACS](https://github.com/mathieumuzelet-hue/SecurityFamily/actions/workflows/hacs.yml/badge.svg)](https://github.com/mathieumuzelet-hue/SecurityFamily/actions/workflows/hacs.yml)

Home Assistant custom integration that locates nearby shelters and guides your household to safety during emergencies.

## Features

- **Real-time shelter detection** using OpenStreetMap (Overpass API)
- **Threat-aware scoring** — different shelters for storms, earthquakes, attacks, floods, etc.
- **Push notifications** with navigation links to the best shelter for each person
- **Adaptive search radius** — automatically expands if few shelters are nearby
- **Webhook support** for external alert triggers (FR-Alert compatible)
- **Custom POIs** — add your own shelters (basement, neighbor's house, etc.)
- **Offline-capable** — local cache ensures the system works without internet
- **Interactive map** — Leaflet-based Lovelace card showing persons and shelters

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** > **+** > Search "Shelter Finder"
3. Install and restart Home Assistant
4. Go to **Settings** > **Devices & Services** > **Add Integration** > "Shelter Finder"

### Manual

1. Copy `custom_components/shelter_finder/` to your HA `custom_components/` directory
2. Restart Home Assistant
3. Add the integration via Settings

## Configuration

### Setup (2 steps)

1. **People & Radius**: Select which `person` entities to track and set the search radius
2. **Threats**: Choose which threat types to enable and the default travel mode

### Options (reconfigurable)

After installation, go to the integration's Options to configure:
- Overpass API URL (for self-hosted instances)
- Cache duration
- Adaptive radius toggle
- Re-notification settings

## Entities

| Entity | Description |
|---|---|
| `sensor.shelter_finder_{person}_nearest` | Name of the nearest/best shelter |
| `sensor.shelter_finder_{person}_distance` | Distance to recommended shelter (m) |
| `sensor.shelter_finder_{person}_eta` | Estimated time of arrival (min) |
| `binary_sensor.shelter_finder_alert` | Whether an alert is active |
| `sensor.shelter_finder_alert_type` | Current threat type |
| `button.shelter_finder_trigger_alert` | Trigger an alert |
| `button.shelter_finder_cancel_alert` | Cancel the active alert |

## Map Card

After installation, add the Shelter Finder map to your dashboard:

1. Edit your dashboard
2. Click **+** (Add Card)
3. Search for "Shelter Finder Map"
4. Configure the card:

```yaml
type: custom:shelter-map-card
title: Shelter Finder
entities:
  - person.alice
  - person.bob
default_zoom: 13
height: 400px
show_radius: true
```

The card shows:
- **Person markers** — colored circles with initials, positioned by GPS
- **Shelter markers** — icons by type (bunker, subway, school, etc.)
- **Popups** — click a person to see their nearest shelter, click a shelter for details
- **Alert banner** — red banner appears automatically when an alert is active

The map card resource is registered automatically — no YAML editing needed.

## Services

| Service | Description |
|---|---|
| `shelter_finder.trigger_alert` | Trigger alert with a specific threat type |
| `shelter_finder.cancel_alert` | Cancel the current alert |
| `shelter_finder.refresh_shelters` | Force refresh shelter cache |
| `shelter_finder.add_custom_poi` | Add a custom shelter location |
| `shelter_finder.confirm_safe` | Confirm a person has reached safety |

## Webhook

External systems can trigger alerts via webhook:

```bash
curl -X POST https://your-ha-instance/api/webhook/sf_xxxx \
  -H "Content-Type: application/json" \
  -d '{"threat_type": "storm", "source": "fr-alert"}'
```

The webhook ID is shown in the integration's Options.

## Threat Types

| Type | Key | Priority Shelters |
|---|---|---|
| Storm | `storm` | Metro stations, bunkers, public buildings |
| Earthquake | `earthquake` | Open spaces, sports centers |
| Attack | `attack` | Bunkers, metro, civic buildings |
| Armed conflict | `armed_conflict` | Bunkers, metro stations |
| Flood | `flood` | Civic buildings, schools, high ground |
| Nuclear/Chemical | `nuclear_chemical` | Bunkers, sealed underground |

## Custom Scores

Override the default threat/shelter scoring by creating `shelter_finder_scores.yaml` in your HA config directory.

## License

MIT
