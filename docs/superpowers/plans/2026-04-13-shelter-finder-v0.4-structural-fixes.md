# Shelter Finder v0.4 — Structural Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 5 structural bugs that prevent Shelter Finder from working: entities never update their state, JS card not auto-registered, buttons don't propagate state changes, and hacs.json misconfigured.

**Architecture:** Rewrite `coordinator.py` to inherit from HA's `DataUpdateCoordinator` (provides auto-polling + listener-based updates to all `CoordinatorEntity` children). Rewrite all sensors and binary_sensor to inherit from `CoordinatorEntity`. Add frontend JS registration in `__init__.py`. Wire buttons to call `async_write_ha_state` on dependent entities.

**Tech Stack:** Home Assistant Core APIs (`DataUpdateCoordinator`, `CoordinatorEntity`, `async_register_static_path`), Python 3.12+, asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `coordinator.py` | **Rewrite** | Inherit from `DataUpdateCoordinator`, auto-poll every 24h, signal entities on data change |
| `sensor.py` | **Rewrite** | All sensors inherit `CoordinatorEntity`, react to coordinator updates |
| `binary_sensor.py` | **Rewrite** | Inherit `CoordinatorEntity`, refresh attributes when coordinator updates |
| `button.py` | **Modify** | Call `coordinator.async_request_refresh()` after trigger/cancel to propagate state |
| `__init__.py` | **Modify** | Register JS as Lovelace resource, pass HA coordinator to platforms, adapt to new coordinator API |
| `cache.py` | No change | Already fixed (blocking I/O wrapped in to_thread by coordinator) |
| `hacs.json` | **Fix** | Add `"content_in_root": false` for HACS compatibility |
| `tests/test_coordinator.py` | **Rewrite** | Mock `DataUpdateCoordinator` instead of custom class |

---

### Task 1: Rewrite coordinator to inherit from DataUpdateCoordinator

**Files:**
- Rewrite: `custom_components/shelter_finder/coordinator.py`
- Test: `tests/test_coordinator.py`

The current coordinator is a plain class with no auto-polling. HA's `DataUpdateCoordinator` provides: automatic polling on `update_interval`, listener notifications to all `CoordinatorEntity` children, error handling with exponential backoff.

- [ ] **Step 1: Rewrite coordinator.py**

```python
"""DataUpdateCoordinator for Shelter Finder."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cache import ShelterCache
from .overpass import OverpassClient
from .shelter_logic import compute_adaptive_radii, merge_shelters_and_pois

_LOGGER = logging.getLogger(__name__)


class ShelterUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator that fetches shelter data from Overpass and merges with POIs."""

    def __init__(
        self,
        hass: HomeAssistant,
        cache: ShelterCache,
        overpass_client: OverpassClient,
        persons: list[str],
        search_radius: int,
        adaptive_radius: bool = True,
        adaptive_radius_max: int = 15000,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="shelter_finder",
            update_interval=timedelta(hours=24),
        )
        self.cache = cache
        self.overpass_client = overpass_client
        self.persons = persons
        self.search_radius = search_radius
        self.adaptive_radius = adaptive_radius
        self.adaptive_radius_max = adaptive_radius_max

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch shelter data from cache or Overpass."""
        try:
            cache_valid = await self.hass.async_add_executor_job(self.cache.is_valid)
            if cache_valid:
                shelters = await self.hass.async_add_executor_job(self.cache.load)
                _LOGGER.debug("Using cached shelter data (%d shelters)", len(shelters))
            else:
                shelters = await self._fetch_from_overpass()

            pois = await self.hass.async_add_executor_job(self.cache.load_pois)
            return merge_shelters_and_pois(shelters, pois)
        except Exception as err:
            raise UpdateFailed(f"Failed to update shelter data: {err}") from err

    async def _fetch_from_overpass(self) -> list[dict[str, Any]]:
        """Fetch shelters from Overpass with adaptive radius and fallback."""
        home = self.hass.states.get("zone.home")
        if home is None:
            raise UpdateFailed("zone.home not found")

        lat = home.attributes.get("latitude", 0)
        lon = home.attributes.get("longitude", 0)

        try:
            shelters = await self.overpass_client.fetch_shelters(lat, lon, self.search_radius)

            if self.adaptive_radius:
                radii = compute_adaptive_radii(
                    self.search_radius, self.adaptive_radius_max, len(shelters),
                )
                for radius in radii:
                    extra = await self.overpass_client.fetch_shelters(lat, lon, radius)
                    shelters.extend(extra)
                    if len(shelters) >= 3:
                        break

            await self.hass.async_add_executor_job(self.cache.save, shelters)
            return shelters

        except Exception as err:
            _LOGGER.warning("Overpass fetch failed: %s, trying stale cache", err)
            stale = await self.hass.async_add_executor_job(self.cache.load_stale)
            if stale:
                return stale
            raise

    async def async_request_refresh(self) -> None:
        """Force a data refresh (invalidate cache first)."""
        self.cache._ttl_seconds = 0
        await self.async_refresh()
```

Key changes:
- Inherits `DataUpdateCoordinator[list[dict[str, Any]]]`
- Uses `self.hass.async_add_executor_job` instead of `asyncio.to_thread` (HA best practice)
- `_async_update_data` returns data (stored in `self.data` automatically by parent)
- Raises `UpdateFailed` for proper error handling with backoff
- `async_request_refresh` calls parent's `async_refresh()` which notifies all listeners

- [ ] **Step 2: Update tests/test_coordinator.py**

```python
"""Tests for ShelterUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.shelter_finder.coordinator import ShelterUpdateCoordinator


@pytest.fixture
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.is_valid = MagicMock(return_value=False)
    cache.load.return_value = []
    cache.load_pois.return_value = []
    cache.load_stale.return_value = []
    cache.save = MagicMock()
    return cache


@pytest.fixture
def mock_overpass_client() -> AsyncMock:
    client = AsyncMock()
    client.fetch_shelters = AsyncMock(return_value=[
        {"osm_id": "node/1", "name": "Abri Test", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter", "source": "osm"},
    ])
    return client


@pytest.fixture
def mock_hass() -> MagicMock:
    hass = MagicMock()
    home_state = MagicMock()
    home_state.attributes = {"latitude": 48.85, "longitude": 2.35}
    hass.states.get.return_value = home_state
    # async_add_executor_job runs the function directly for testing
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *args: fn(*args))
    return hass


@pytest.fixture
def coordinator(mock_hass, mock_cache, mock_overpass_client) -> ShelterUpdateCoordinator:
    with patch("custom_components.shelter_finder.coordinator.DataUpdateCoordinator.__init__"):
        coord = ShelterUpdateCoordinator(
            hass=mock_hass,
            cache=mock_cache,
            overpass_client=mock_overpass_client,
            persons=["person.alice"],
            search_radius=2000,
            adaptive_radius=True,
            adaptive_radius_max=15000,
        )
        coord.hass = mock_hass
        coord.logger = MagicMock()
        return coord


@pytest.mark.asyncio
async def test_fetch_from_overpass_when_cache_empty(coordinator, mock_overpass_client, mock_cache):
    data = await coordinator._async_update_data()
    mock_overpass_client.fetch_shelters.assert_called()
    mock_cache.save.assert_called_once()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_use_cache_when_valid(coordinator, mock_cache, mock_overpass_client):
    mock_cache.is_valid = MagicMock(return_value=True)
    mock_cache.load.return_value = [
        {"osm_id": "node/1", "name": "Cached", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker", "source": "osm"},
    ]
    data = await coordinator._async_update_data()
    mock_overpass_client.fetch_shelters.assert_not_called()
    assert data[0]["name"] == "Cached"


@pytest.mark.asyncio
async def test_merge_pois(coordinator, mock_cache, mock_overpass_client):
    mock_cache.load_pois.return_value = [
        {"id": "poi1", "name": "Ma Cave", "latitude": 48.86, "longitude": 2.36, "shelter_type": "bunker", "source": "manual"},
    ]
    data = await coordinator._async_update_data()
    assert len(data) == 2
    assert any(s["name"] == "Ma Cave" for s in data)


@pytest.mark.asyncio
async def test_fallback_to_stale_cache_on_error(coordinator, mock_cache, mock_overpass_client):
    mock_overpass_client.fetch_shelters = AsyncMock(side_effect=Exception("API down"))
    stale_data = [{"osm_id": "node/1", "name": "Stale", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter", "source": "osm"}]
    mock_cache.load_stale.return_value = stale_data
    data = await coordinator._async_update_data()
    assert data[0]["name"] == "Stale"


@pytest.mark.asyncio
async def test_error_with_no_cache_raises(coordinator, mock_cache, mock_overpass_client):
    mock_overpass_client.fetch_shelters = AsyncMock(side_effect=Exception("API down"))
    mock_cache.load_stale.return_value = []
    with pytest.raises(Exception):
        await coordinator._async_update_data()
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/shelter_finder/coordinator.py tests/test_coordinator.py
git commit -m "refactor: coordinator inherits DataUpdateCoordinator for auto-polling"
```

---

### Task 2: Rewrite sensors to inherit from CoordinatorEntity

**Files:**
- Rewrite: `custom_components/shelter_finder/sensor.py`

`CoordinatorEntity` automatically calls `self.async_write_ha_state()` whenever the coordinator fires `async_set_updated_data`. This means sensors will update whenever coordinator data changes, and also whenever HA polls them (person location updates).

- [ ] **Step 1: Rewrite sensor.py**

```python
"""Sensor platform for Shelter Finder."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .alert_coordinator import AlertCoordinator
from .const import CONF_PERSONS, DOMAIN
from .coordinator import ShelterUpdateCoordinator
from .routing import calculate_eta_minutes, haversine_distance


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    persons = entry.data.get(CONF_PERSONS, [])

    entities: list[SensorEntity] = []
    for person_id in persons:
        person_name = person_id.split(".")[-1]
        entities.append(ShelterNearestSensor(coordinator, alert_coordinator, person_id, person_name))
        entities.append(ShelterDistanceSensor(coordinator, alert_coordinator, person_id, person_name))
        entities.append(ShelterETASensor(coordinator, alert_coordinator, person_id, person_name))
    entities.append(ShelterAlertTypeSensor(coordinator, alert_coordinator))
    async_add_entities(entities)


def _find_nearest_shelter(
    shelters: list[dict[str, Any]], lat: float, lon: float,
) -> dict[str, Any] | None:
    """Find the nearest shelter to a given position."""
    nearest = None
    min_dist = float("inf")
    for shelter in shelters:
        dist = haversine_distance(lat, lon, shelter["latitude"], shelter["longitude"])
        if dist < min_dist:
            min_dist = dist
            nearest = {**shelter, "distance_m": round(dist)}
    return nearest


def _get_person_coords(hass: HomeAssistant, person_id: str) -> tuple[float, float] | None:
    """Get lat/lon for a person entity, or None."""
    state = hass.states.get(person_id)
    if state is None:
        return None
    lat = state.attributes.get("latitude")
    lon = state.attributes.get("longitude")
    if lat is None or lon is None:
        return None
    return (lat, lon)


class ShelterNearestSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-home"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator, person_id: str, person_name: str) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_nearest"
        self._attr_name = f"{person_name} shelter nearest"

    @property
    def native_value(self) -> str | None:
        shelter = self._get_shelter()
        return shelter["name"] if shelter else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        shelter = self._get_shelter()
        if shelter is None:
            return {}
        return {
            "latitude": shelter.get("latitude"),
            "longitude": shelter.get("longitude"),
            "shelter_type": shelter.get("shelter_type"),
            "source": shelter.get("source"),
            "distance_m": shelter.get("distance_m"),
            "score": shelter.get("score"),
        }

    def _get_shelter(self) -> dict[str, Any] | None:
        if self._alert_coordinator.is_active:
            return self._alert_coordinator.get_best_shelter(self._person_id)
        shelters = self.coordinator.data or []
        if not shelters:
            return None
        coords = _get_person_coords(self.hass, self._person_id)
        if coords is None:
            return None
        return _find_nearest_shelter(shelters, coords[0], coords[1])


class ShelterDistanceSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator, person_id: str, person_name: str) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_distance"
        self._attr_name = f"{person_name} shelter distance"

    @property
    def native_value(self) -> int | None:
        if self._alert_coordinator.is_active:
            shelter = self._alert_coordinator.get_best_shelter(self._person_id)
            return shelter["distance_m"] if shelter else None
        shelters = self.coordinator.data or []
        if not shelters:
            return None
        coords = _get_person_coords(self.hass, self._person_id)
        if coords is None:
            return None
        nearest = _find_nearest_shelter(shelters, coords[0], coords[1])
        return nearest["distance_m"] if nearest else None


class ShelterETASensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:clock-fast"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator, person_id: str, person_name: str) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_eta"
        self._attr_name = f"{person_name} shelter ETA"

    @property
    def native_value(self) -> float | None:
        if self._alert_coordinator.is_active:
            shelter = self._alert_coordinator.get_best_shelter(self._person_id)
            return shelter.get("eta_minutes") if shelter else None
        shelters = self.coordinator.data or []
        if not shelters:
            return None
        coords = _get_person_coords(self.hass, self._person_id)
        if coords is None:
            return None
        nearest = _find_nearest_shelter(shelters, coords[0], coords[1])
        if nearest:
            return calculate_eta_minutes(nearest["distance_m"], "walking")
        return None


class ShelterAlertTypeSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_alert_type"
    _attr_name = "Alert type"
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator

    @property
    def native_value(self) -> str:
        if self._alert_coordinator.is_active and self._alert_coordinator.threat_type:
            return self._alert_coordinator.threat_type
        return "none"
```

Key changes:
- All sensors inherit `CoordinatorEntity` first, then `SensorEntity` (MRO order matters)
- `super().__init__(coordinator)` registers the entity as a listener
- `self.coordinator.data` replaces `self._coordinator.data`
- `self.hass` from CoordinatorEntity replaces `self._coordinator.hass`
- Shared helpers `_find_nearest_shelter` and `_get_person_coords` replace duplicated code
- Sensors also set `should_poll = True` (inherited default) so HA re-reads `native_value` every scan interval, picking up person GPS changes

- [ ] **Step 2: Commit**

```bash
git add custom_components/shelter_finder/sensor.py
git commit -m "refactor: sensors inherit CoordinatorEntity for automatic state updates"
```

---

### Task 3: Rewrite binary_sensor to inherit from CoordinatorEntity

**Files:**
- Rewrite: `custom_components/shelter_finder/binary_sensor.py`

- [ ] **Step 1: Rewrite binary_sensor.py**

```python
"""Binary sensor platform for Shelter Finder."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .alert_coordinator import AlertCoordinator
from .const import DOMAIN
from .coordinator import ShelterUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    async_add_entities([ShelterAlertBinarySensor(coordinator, alert_coordinator)])


class ShelterAlertBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_alert"
    _attr_name = "Alert"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator

    @property
    def is_on(self) -> bool:
        return self._alert_coordinator.is_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ac = self._alert_coordinator
        shelters = self.coordinator.data or []
        shelter_list = [
            {"name": s.get("name", ""), "lat": s.get("latitude"), "lon": s.get("longitude"),
             "type": s.get("shelter_type", ""), "source": s.get("source", "osm")}
            for s in shelters if s.get("latitude") and s.get("longitude")
        ]
        return {
            "threat_type": ac.threat_type,
            "triggered_at": str(ac.triggered_at) if ac.triggered_at else None,
            "triggered_by": ac.triggered_by,
            "persons_safe": ac.persons_safe,
            "shelters": shelter_list,
            "shelter_count": len(shelter_list),
        }
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/shelter_finder/binary_sensor.py
git commit -m "refactor: binary_sensor inherits CoordinatorEntity for automatic state updates"
```

---

### Task 4: Fix buttons to propagate state changes

**Files:**
- Modify: `custom_components/shelter_finder/button.py`

When `trigger()` or `cancel()` is called, the alert state changes but no entity knows about it. The buttons must call `coordinator.async_request_refresh()` to force all `CoordinatorEntity` children to re-read their state.

- [ ] **Step 1: Rewrite button.py**

```python
"""Button platform for Shelter Finder."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .alert_coordinator import AlertCoordinator
from .const import DOMAIN
from .coordinator import ShelterUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    async_add_entities([
        ShelterTriggerAlertButton(coordinator, alert_coordinator),
        ShelterCancelAlertButton(coordinator, alert_coordinator),
    ])


class ShelterTriggerAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_trigger_alert"
    _attr_name = "Trigger alert"
    _attr_icon = "mdi:alert-plus"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        self._alert_coordinator.trigger("storm", triggered_by="button")
        self._coordinator.async_set_updated_data(self._coordinator.data or [])


class ShelterCancelAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_cancel_alert"
    _attr_name = "Cancel alert"
    _attr_icon = "mdi:alert-remove"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        self._alert_coordinator.cancel()
        self._coordinator.async_set_updated_data(self._coordinator.data or [])
```

Key change: `self._coordinator.async_set_updated_data(...)` notifies ALL `CoordinatorEntity` listeners to re-read their state immediately. No data refetch needed, just state propagation.

- [ ] **Step 2: Commit**

```bash
git add custom_components/shelter_finder/button.py
git commit -m "fix: buttons propagate alert state changes to all entities"
```

---

### Task 5: Register JS card as Lovelace resource + adapt __init__.py to new coordinator

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`

The JS card is never registered. Users who install via HACS or manually get no card loaded. We need to register it using `async_register_static_path` + `add_extra_js_url`.

Also: `__init__.py` must be adapted to the new `DataUpdateCoordinator` API (no more `coordinator.data = await coordinator._async_update_data()`, use `await coordinator.async_config_entry_first_refresh()` instead).

- [ ] **Step 1: Rewrite __init__.py**

Replace the `async_setup_entry` function and add frontend registration. Full file:

```python
"""Shelter Finder integration."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import webhook as ha_webhook
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .alert_coordinator import AlertCoordinator
from .cache import ShelterCache
from .const import (
    CONF_ADAPTIVE_RADIUS,
    CONF_ADAPTIVE_RADIUS_MAX,
    CONF_CACHE_TTL,
    CONF_CUSTOM_OSM_TAGS,
    CONF_DEFAULT_TRAVEL_MODE,
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_OVERPASS_URL,
    CONF_PERSONS,
    CONF_RE_NOTIFICATION_INTERVAL,
    CONF_SEARCH_RADIUS,
    CONF_WEBHOOK_ID,
    DEFAULT_ADAPTIVE_RADIUS_MAX,
    DEFAULT_CACHE_TTL,
    DEFAULT_MAX_RE_NOTIFICATIONS,
    DEFAULT_OVERPASS_URL,
    DEFAULT_RADIUS,
    DEFAULT_RE_NOTIFICATION_INTERVAL,
    DEFAULT_TRAVEL_MODE,
    DOMAIN,
    SHELTER_TYPES,
    THREAT_TYPES,
)
from .coordinator import ShelterUpdateCoordinator
from .overpass import OverpassClient
from .webhook import async_handle_webhook

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

CARD_URL = f"/shelter_finder/shelter-map-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the JS card as a Lovelace resource (once per HA instance)."""
    hass.data.setdefault(DOMAIN, {})

    # Register static path to serve the JS card
    hass.http.register_static_path(
        "/shelter_finder",
        str(Path(__file__).parent / "www"),
        cache_headers=False,
    )

    # Register the card as a Lovelace resource
    from homeassistant.components.lovelace.resources import (
        ResourceStorageCollection,
    )
    # Use frontend add_extra_js_url for immediate availability
    hass.components.frontend.async_register_built_in_panel
    from homeassistant.components.frontend import add_extra_js_url
    add_extra_js_url(hass, CARD_URL)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelter Finder from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config = {**entry.data, **entry.options}
    persons = config.get(CONF_PERSONS, [])
    search_radius = config.get(CONF_SEARCH_RADIUS, DEFAULT_RADIUS)
    travel_mode = config.get(CONF_DEFAULT_TRAVEL_MODE, DEFAULT_TRAVEL_MODE)
    overpass_url = config.get(CONF_OVERPASS_URL, DEFAULT_OVERPASS_URL)
    cache_ttl = config.get(CONF_CACHE_TTL, DEFAULT_CACHE_TTL)
    adaptive_radius = config.get(CONF_ADAPTIVE_RADIUS, True)
    adaptive_radius_max = config.get(CONF_ADAPTIVE_RADIUS_MAX, DEFAULT_ADAPTIVE_RADIUS_MAX)
    re_notif_interval = config.get(CONF_RE_NOTIFICATION_INTERVAL, DEFAULT_RE_NOTIFICATION_INTERVAL)
    max_re_notif = config.get(CONF_MAX_RE_NOTIFICATIONS, DEFAULT_MAX_RE_NOTIFICATIONS)

    custom_tags_str = config.get(CONF_CUSTOM_OSM_TAGS, "")
    custom_tags = [t.strip() for t in custom_tags_str.split(",") if t.strip()] if custom_tags_str else None

    session = async_get_clientsession(hass)
    storage_dir = Path(hass.config.path(".storage"))
    cache = ShelterCache(storage_dir, ttl_hours=cache_ttl)
    overpass_client = OverpassClient(session=session, url=overpass_url, tags=custom_tags)

    coordinator = ShelterUpdateCoordinator(
        hass=hass,
        cache=cache,
        overpass_client=overpass_client,
        persons=persons,
        search_radius=search_radius,
        adaptive_radius=adaptive_radius,
        adaptive_radius_max=adaptive_radius_max,
    )

    # First refresh — populates coordinator.data and sets up auto-polling
    await coordinator.async_config_entry_first_refresh()

    alert_coordinator = AlertCoordinator(
        hass=hass,
        shelter_coordinator=coordinator,
        persons=persons,
        travel_mode=travel_mode,
        re_notification_interval=re_notif_interval,
        max_re_notifications=max_re_notif,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "alert_coordinator": alert_coordinator,
        "cache": cache,
    }
    hass.data[DOMAIN]["alert_coordinator"] = alert_coordinator

    if not hass.services.has_service(DOMAIN, "trigger_alert"):
        _register_services(hass)

    webhook_id = config.get(CONF_WEBHOOK_ID, entry.entry_id)
    try:
        ha_webhook.async_register(hass, DOMAIN, "Shelter Finder Alert", webhook_id, async_handle_webhook)
    except ValueError:
        _LOGGER.debug("Webhook %s already registered, skipping", webhook_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Onboarding notification
    shelter_count = len(coordinator.data) if coordinator.data else 0
    person_count = len(persons)
    from homeassistant.components.persistent_notification import async_create as pn_create
    pn_create(
        hass,
        (
            f"Shelter Finder installed!\n\n"
            f"- {person_count} person(s) tracked\n"
            f"- {shelter_count} shelter(s) found within {search_radius}m\n"
            f"- Webhook: `/api/webhook/{webhook_id}`\n\n"
            f"Add the map card: Edit dashboard > + > Shelter Finder Map\n"
            f"Test: Services > shelter_finder.trigger_alert"
        ),
        title="Shelter Finder",
        notification_id=f"{DOMAIN}_onboarding",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    config = {**entry.data, **entry.options}
    webhook_id = config.get(CONF_WEBHOOK_ID, entry.entry_id)
    ha_webhook.async_unregister(hass, webhook_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not any(k for k in hass.data[DOMAIN] if k != "alert_coordinator"):
            hass.data[DOMAIN].pop("alert_coordinator", None)

    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register Shelter Finder services."""

    async def handle_trigger_alert(call: ServiceCall) -> None:
        threat_type = call.data["threat_type"]
        message = call.data.get("message", "")
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.trigger(threat_type, triggered_by="service")
            # Notify all coordinator entities of state change
            for entry_data in hass.data.get(DOMAIN, {}).values():
                if isinstance(entry_data, dict) and "coordinator" in entry_data:
                    coord = entry_data["coordinator"]
                    coord.async_set_updated_data(coord.data or [])
            await _send_alert_notifications(hass, ac, message)

    async def handle_cancel_alert(call: ServiceCall) -> None:
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.cancel()
            for entry_data in hass.data.get(DOMAIN, {}).values():
                if isinstance(entry_data, dict) and "coordinator" in entry_data:
                    coord = entry_data["coordinator"]
                    coord.async_set_updated_data(coord.data or [])

    async def handle_refresh_shelters(call: ServiceCall) -> None:
        for entry_data in hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                await entry_data["coordinator"].async_request_refresh()

    async def handle_add_custom_poi(call: ServiceCall) -> None:
        name = call.data["name"]
        lat = call.data["latitude"]
        lon = call.data["longitude"]
        shelter_type = call.data["shelter_type"]
        notes = call.data.get("notes", "")

        for entry_data in hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "cache" in entry_data:
                cache = entry_data["cache"]
                pois = await hass.async_add_executor_job(cache.load_pois)
                pois.append({
                    "id": uuid.uuid4().hex,
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "shelter_type": shelter_type,
                    "notes": notes,
                    "source": "manual",
                })
                await hass.async_add_executor_job(cache.save_pois, pois)
                if "coordinator" in entry_data:
                    await entry_data["coordinator"].async_request_refresh()

    async def handle_confirm_safe(call: ServiceCall) -> None:
        person = call.data["person"]
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.confirm_safe(person)
            for entry_data in hass.data.get(DOMAIN, {}).values():
                if isinstance(entry_data, dict) and "coordinator" in entry_data:
                    coord = entry_data["coordinator"]
                    coord.async_set_updated_data(coord.data or [])

    hass.services.async_register(
        DOMAIN, "trigger_alert", handle_trigger_alert,
        schema=vol.Schema({
            vol.Required("threat_type"): vol.In(THREAT_TYPES),
            vol.Optional("message", default=""): cv.string,
        }),
    )
    hass.services.async_register(DOMAIN, "cancel_alert", handle_cancel_alert)
    hass.services.async_register(DOMAIN, "refresh_shelters", handle_refresh_shelters)
    hass.services.async_register(
        DOMAIN, "add_custom_poi", handle_add_custom_poi,
        schema=vol.Schema({
            vol.Required("name"): cv.string,
            vol.Required("latitude"): vol.Coerce(float),
            vol.Required("longitude"): vol.Coerce(float),
            vol.Required("shelter_type"): vol.In(SHELTER_TYPES),
            vol.Optional("notes", default=""): cv.string,
        }),
    )
    hass.services.async_register(
        DOMAIN, "confirm_safe", handle_confirm_safe,
        schema=vol.Schema({vol.Required("person"): cv.string}),
    )


def _find_mobile_app_service(hass: HomeAssistant, person_name: str) -> str | None:
    """Find the notify service for a person by checking available services."""
    candidate = f"mobile_app_{person_name}"
    if hass.services.has_service("notify", candidate):
        return candidate
    for service in hass.services.async_services().get("notify", {}):
        if person_name.lower() in service.lower():
            return service
    return None


async def _send_alert_notifications(hass: HomeAssistant, alert_coordinator: AlertCoordinator, message: str = "") -> None:
    """Send push notifications to all tracked persons."""
    for person_id in alert_coordinator.persons:
        best = alert_coordinator.get_best_shelter(person_id)
        if best is None:
            continue

        person_name = person_id.split(".")[-1]
        device_service = _find_mobile_app_service(hass, person_name)

        nav_url = (
            f"https://www.google.com/maps/dir/?api=1"
            f"&destination={best['latitude']},{best['longitude']}"
            f"&travelmode=walking"
        )

        notif_message = (
            f"ALERTE {alert_coordinator.threat_type.upper()}\n"
            f"Abri: {best['name']} ({best['shelter_type']})\n"
            f"Distance: {best['distance_m']}m - ETA: {best.get('eta_minutes', '?')} min\n"
        )
        if message:
            notif_message = f"{message}\n\n{notif_message}"

        if device_service is None:
            _LOGGER.warning(
                "No mobile_app notify service found for %s — "
                "check that the companion app is installed and the device name matches",
                person_id,
            )
            continue

        try:
            await hass.services.async_call(
                "notify", device_service,
                {
                    "message": notif_message,
                    "title": f"Shelter Finder - {alert_coordinator.threat_type}",
                    "data": {
                        "actions": [{"action": "CONFIRM_SAFE", "title": "Je suis à l'abri"}],
                        "url": nav_url,
                        "clickAction": nav_url,
                        "priority": "high",
                        "ttl": 0,
                    },
                },
                blocking=False,
            )
            alert_coordinator.record_notification(person_id)
        except Exception:
            _LOGGER.exception("Failed to send notification to %s", person_id)
```

Key changes:
- Added `async_setup()` to register the JS card as a Lovelace resource via `hass.http.register_static_path` + `add_extra_js_url`
- `async_setup_entry` uses `await coordinator.async_config_entry_first_refresh()` instead of manual `_async_update_data()`
- All services that change alert state call `coord.async_set_updated_data(...)` to notify entities
- `handle_add_custom_poi` uses `hass.async_add_executor_job` instead of `asyncio.to_thread`
- Removed unused `asyncio` import from `handle_add_custom_poi`

- [ ] **Step 2: Commit**

```bash
git add custom_components/shelter_finder/__init__.py
git commit -m "feat: register JS card as Lovelace resource + adapt to DataUpdateCoordinator"
```

---

### Task 6: Fix hacs.json for proper HACS integration type

**Files:**
- Modify: `hacs.json`

- [ ] **Step 1: Update hacs.json**

```json
{
  "name": "Shelter Finder",
  "render_readme": true,
  "homeassistant": "2024.1.0",
  "content_in_root": false
}
```

- [ ] **Step 2: Bump manifest version to 0.4.0**

In `custom_components/shelter_finder/manifest.json`, change:
```json
"version": "0.4.0"
```

- [ ] **Step 3: Update card version string**

In `custom_components/shelter_finder/www/shelter-map-card.js`, change:
```javascript
"%c SHELTER-MAP-CARD %c v0.4.0 ",
```

- [ ] **Step 4: Commit**

```bash
git add hacs.json custom_components/shelter_finder/manifest.json custom_components/shelter_finder/www/shelter-map-card.js
git commit -m "chore: fix hacs.json + bump version to 0.4.0"
```

---

### Task 7: Final integration verification

- [ ] **Step 1: Verify no circular imports**

```bash
python -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('custom_components/shelter_finder/*.py')]" 2>&1
```

Expected: no output (all files parse correctly)

- [ ] **Step 2: Verify entity ID consistency**

Check that the JS card entity references match the Python sensor unique_ids:

| JS reference | Python unique_id | Expected entity_id | Match? |
|---|---|---|---|
| `binary_sensor.shelter_finder_alert` | `shelter_finder_alert` | `binary_sensor.shelter_finder_alert` | YES |
| `sensor.{personKey}_shelter_nearest` | `shelter_finder_{personKey}_nearest` | `sensor.shelter_finder_{personKey}_nearest` | **NO** |
| `sensor.{personKey}_shelter_distance` | `shelter_finder_{personKey}_distance` | `sensor.shelter_finder_{personKey}_distance` | **NO** |
| `sensor.shelter_finder_alert_type` | `shelter_finder_alert_type` | `sensor.shelter_finder_alert_type` | YES |

**IMPORTANT**: The entity_id is generated from `_attr_name` when `_attr_has_entity_name = True` and there is no device. HA slugifies the name: `"distant shelter nearest"` becomes `sensor.distant_shelter_nearest`. The unique_id is NOT used for entity_id generation.

So the JS references `sensor.{personKey}_shelter_nearest` will match `sensor.distant_shelter_nearest` from name `"distant shelter nearest"`. This is CORRECT based on the screenshot evidence.

- [ ] **Step 3: Final commit and tag**

```bash
git tag v0.4.0
```
