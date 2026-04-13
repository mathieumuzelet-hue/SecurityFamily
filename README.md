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
| `sensor.{person}_shelter_nearest` | Name of the nearest/best shelter |
| `sensor.{person}_shelter_distance` | Distance to recommended shelter (m) |
| `sensor.{person}_shelter_eta` | Estimated time of arrival (min) |
| `binary_sensor.alert` | Whether an alert is active |
| `sensor.alert_type` | Current threat type |
| `button.trigger_alert` | Trigger an alert |
| `button.cancel_alert` | Cancel the active alert |

The `nearest` sensor also exposes `latitude`, `longitude`, `shelter_type`, `distance_m`, and `source` as attributes.

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
- **Recommended shelter** — star marker with pulsing glow for each person's best option
- **Route lines** — dashed line connecting each person to their recommended shelter
- **Popups** — click a person to see their nearest shelter + distance + ETA
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

## Automation Ideas

Shelter Finder exposes enough data to build powerful safety automations. Here are ready-to-use examples.

### Auto-trigger alert from weather warnings

Use the Met Office or Meteorologisk Institutt integration to trigger shelter alerts when severe weather is detected:

```yaml
automation:
  - alias: "Shelter alert on storm warning"
    trigger:
      - platform: state
        entity_id: weather.home
        attribute: forecast
    condition:
      - condition: template
        value_template: >
          {{ state_attr('weather.home', 'forecast')
             | selectattr('condition', 'in', ['lightning-rainy', 'hail', 'exceptional'])
             | list | count > 0 }}
    action:
      - service: shelter_finder.trigger_alert
        data:
          threat_type: storm
          message: "Alerte meteo automatique"
```

### Notify when a family member is far from any shelter

Send a notification if someone is more than 5km from the nearest shelter:

```yaml
automation:
  - alias: "Far from shelter warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.distant_shelter_distance
        above: 5000
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Shelter Finder"
          message: >
            {{ state_attr('sensor.distant_shelter_nearest', 'friendly_name').split(' ')[-1] }}
            est a {{ states('sensor.distant_shelter_distance') }}m du premier abri.
```

### Send navigation link on alert

When an alert triggers, send each person a Google Maps navigation link to their recommended shelter:

```yaml
automation:
  - alias: "Navigation to shelter on alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.alert
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "ALERTE {{ states('sensor.alert_type') | upper }}"
          message: >
            Abri: {{ states('sensor.distant_shelter_nearest') }}
            ({{ states('sensor.distant_shelter_distance') }}m, ~{{ states('sensor.distant_shelter_eta') }} min)
          data:
            url: >
              https://www.google.com/maps/dir/?api=1
              &destination={{ state_attr('sensor.distant_shelter_nearest', 'latitude') }},{{ state_attr('sensor.distant_shelter_nearest', 'longitude') }}
              &travelmode=walking
            priority: high
```

### Dashboard card showing shelter status

Add a conditional card that changes based on alert state:

```yaml
type: conditional
conditions:
  - entity: binary_sensor.alert
    state: "on"
card:
  type: markdown
  content: >
    ## ALERTE {{ states('sensor.alert_type') | upper }}

    | Personne | Abri | Distance | ETA |
    |---|---|---|---|
    | Distant | {{ states('sensor.distant_shelter_nearest') }} | {{ states('sensor.distant_shelter_distance') }}m | {{ states('sensor.distant_shelter_eta') }} min |
    | Delphine | {{ states('sensor.delphine_shelter_nearest') }} | {{ states('sensor.delphine_shelter_distance') }}m | {{ states('sensor.delphine_shelter_eta') }} min |
```

### Webhook integration with FR-Alert

Trigger Shelter Finder from external alert systems using the webhook:

```yaml
# Call from any system (curl, Node-RED, n8n, etc.)
# The webhook ID is shown in Settings > Integrations > Shelter Finder
curl -X POST https://your-ha/api/webhook/sf_xxxx \
  -H "Content-Type: application/json" \
  -d '{"threat_type": "attack", "source": "fr-alert"}'
```

### Auto-cancel alert when everyone is safe

```yaml
automation:
  - alias: "Auto cancel when all safe"
    trigger:
      - platform: template
        value_template: >
          {{ is_state('binary_sensor.alert', 'on')
             and state_attr('binary_sensor.alert', 'persons_safe') | length
                == state_attr('binary_sensor.alert', 'persons_safe') | length }}
    condition:
      - condition: state
        entity_id: binary_sensor.alert
        state: "on"
    action:
      - service: shelter_finder.cancel_alert
      - service: notify.mobile_app_your_phone
        data:
          title: "Shelter Finder"
          message: "Tout le monde est en securite. Alerte annulee."
```

### Track shelter proximity over time

Add `sensor.{person}_shelter_distance` to a history graph to see how close each family member typically is to a shelter during their daily routine:

```yaml
type: history-graph
entities:
  - entity: sensor.distant_shelter_distance
  - entity: sensor.delphine_shelter_distance
hours_to_show: 168
title: Distance aux abris (7 jours)
```

## Custom Scores

Override the default threat/shelter scoring by creating `shelter_finder_scores.yaml` in your HA config directory.

## License

MIT
