# Shelter Finder v0.1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a working Home Assistant custom component that detects nearby shelters via Overpass/OSM, alerts household members with push notifications and navigation links, and supports webhook-triggered alerts.

**Architecture:** Custom component (`custom_components/shelter_finder/`) with two coordinators — `ShelterUpdateCoordinator` for slow-cycle Overpass cache (24h) and `AlertCoordinator` for real-time alert state. Entities: sensors per person (nearest, distance, ETA), global binary sensor (alert active), buttons (trigger/cancel), alert type sensor. Webhook endpoint for external triggers.

**Tech Stack:** Python 3.12+, Home Assistant Core 2024.1+, aiohttp (built-in HA), pytest + pytest-homeassistant-custom-component, GitHub Actions CI.

**Design doc:** `docs/superpowers/specs/2026-04-13-shelter-finder-design.md`

---

## File Map

| File | Responsibility | Created in Task |
|---|---|---|
| `custom_components/shelter_finder/manifest.json` | HA integration metadata | 1 |
| `custom_components/shelter_finder/const.py` | Constants, threat types, OSM tags, scores | 1 |
| `custom_components/shelter_finder/hacs.json` (root) | HACS distribution metadata | 1 |
| `tests/conftest.py` | pytest fixtures, HA mocks | 1 |
| `custom_components/shelter_finder/cache.py` | JSON file cache with TTL | 2 |
| `tests/test_cache.py` | Cache tests | 2 |
| `custom_components/shelter_finder/overpass.py` | Overpass API client | 3 |
| `tests/test_overpass.py` | Overpass tests | 3 |
| `custom_components/shelter_finder/shelter_logic.py` | Scoring, ranking, adaptive radius | 4 |
| `tests/test_shelter_logic.py` | Shelter logic tests | 4 |
| `custom_components/shelter_finder/routing.py` | Haversine distance + ETA | 5 |
| `tests/test_routing.py` | Routing tests | 5 |
| `custom_components/shelter_finder/coordinator.py` | ShelterUpdateCoordinator (Overpass polling) | 6 |
| `tests/test_coordinator.py` | Coordinator tests | 6 |
| `custom_components/shelter_finder/alert_coordinator.py` | Alert state, GPS refresh, notifications | 7 |
| `tests/test_alert_coordinator.py` | Alert coordinator tests | 7 |
| `custom_components/shelter_finder/config_flow.py` | 2-step config flow + OptionsFlow | 8 |
| `custom_components/shelter_finder/strings.json` | UI strings (en) | 8 |
| `custom_components/shelter_finder/translations/en.json` | English translations | 8 |
| `custom_components/shelter_finder/translations/fr.json` | French translations | 8 |
| `tests/test_config_flow.py` | Config flow tests | 8 |
| `custom_components/shelter_finder/sensor.py` | Nearest, distance, ETA, alert_type sensors | 9 |
| `tests/test_sensor.py` | Sensor tests | 9 |
| `custom_components/shelter_finder/binary_sensor.py` | Alert active binary sensor | 10 |
| `tests/test_binary_sensor.py` | Binary sensor tests | 10 |
| `custom_components/shelter_finder/button.py` | Trigger/cancel alert buttons | 11 |
| `tests/test_button.py` | Button tests | 11 |
| `custom_components/shelter_finder/webhook.py` | Webhook handler | 12 |
| `tests/test_webhook.py` | Webhook tests | 12 |
| `custom_components/shelter_finder/services.yaml` | Service definitions | 13 |
| `custom_components/shelter_finder/__init__.py` | Integration setup, services, onboarding | 13 |
| `tests/test_init.py` | Init tests | 13 |
| `.github/workflows/tests.yml` | CI: pytest | 14 |
| `.github/workflows/hacs.yml` | CI: HACS validation | 14 |
| `requirements_test.txt` | Test dependencies | 14 |
| `README.md` | User documentation | 15 |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `custom_components/shelter_finder/manifest.json`
- Create: `custom_components/shelter_finder/const.py`
- Create: `custom_components/shelter_finder/__init__.py` (stub)
- Create: `hacs.json`
- Create: `tests/conftest.py`
- Create: `requirements_test.txt`
- Create: `setup.cfg`

- [ ] **Step 1: Create manifest.json**

```json
{
  "domain": "shelter_finder",
  "name": "Shelter Finder",
  "version": "0.1.0",
  "codeowners": ["@mathieumuzelet-hue"],
  "config_flow": true,
  "dependencies": ["http", "webhook"],
  "documentation": "https://github.com/mathieumuzelet-hue/SecurityFamily",
  "integration_type": "hub",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/mathieumuzelet-hue/SecurityFamily/issues",
  "requirements": [],
  "loggers": ["custom_components.shelter_finder"]
}
```

- [ ] **Step 2: Create const.py**

```python
"""Constants for Shelter Finder."""

from __future__ import annotations

DOMAIN = "shelter_finder"

# Config keys
CONF_PERSONS = "persons"
CONF_SEARCH_RADIUS = "search_radius"
CONF_LANGUAGE = "language"
CONF_ENABLED_THREATS = "enabled_threats"
CONF_DEFAULT_TRAVEL_MODE = "default_travel_mode"
CONF_OVERPASS_URL = "overpass_url"
CONF_CACHE_TTL = "cache_ttl"
CONF_OSRM_ENABLED = "osrm_enabled"
CONF_OSRM_URL = "osrm_url"
CONF_CUSTOM_OSM_TAGS = "custom_osm_tags"
CONF_WEBHOOK_ID = "webhook_id"
CONF_RE_NOTIFICATION_INTERVAL = "re_notification_interval"
CONF_MAX_RE_NOTIFICATIONS = "max_re_notifications"
CONF_ADAPTIVE_RADIUS = "adaptive_radius"
CONF_ADAPTIVE_RADIUS_MAX = "adaptive_radius_max"

# Defaults
DEFAULT_RADIUS = 2000
DEFAULT_LANGUAGE = "fr"
DEFAULT_TRAVEL_MODE = "walking"
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_CACHE_TTL = 24  # hours
DEFAULT_RE_NOTIFICATION_INTERVAL = 5  # minutes
DEFAULT_MAX_RE_NOTIFICATIONS = 3
DEFAULT_ADAPTIVE_RADIUS_MAX = 15000  # meters
ADAPTIVE_RADIUS_MIN_RESULTS = 3

# Threat types
THREAT_TYPES = [
    "storm",
    "earthquake",
    "attack",
    "armed_conflict",
    "flood",
    "nuclear_chemical",
]

# Shelter types
SHELTER_TYPES = [
    "subway",
    "bunker",
    "civic",
    "school",
    "worship",
    "shelter",
    "sports",
    "hospital",
    "government",
    "open_space",
]

# Threat → shelter scoring matrix
THREAT_SHELTER_SCORES: dict[str, dict[str, int]] = {
    "storm": {"subway": 10, "bunker": 9, "civic": 8, "school": 7, "worship": 6, "shelter": 5, "sports": 4, "hospital": 3, "government": 3, "open_space": 1},
    "earthquake": {"open_space": 10, "sports": 7, "shelter": 5, "school": 4, "subway": 2, "bunker": 2, "civic": 3, "worship": 3, "hospital": 4, "government": 3},
    "attack": {"bunker": 10, "subway": 9, "civic": 7, "worship": 6, "school": 5, "hospital": 4, "government": 6, "shelter": 3, "sports": 2, "open_space": 1},
    "armed_conflict": {"bunker": 10, "subway": 10, "civic": 6, "school": 5, "hospital": 4, "government": 5, "worship": 4, "shelter": 3, "sports": 2, "open_space": 1},
    "flood": {"civic": 8, "school": 7, "worship": 6, "sports": 5, "hospital": 7, "government": 7, "shelter": 4, "open_space": 3, "subway": 1, "bunker": 1},
    "nuclear_chemical": {"bunker": 10, "subway": 8, "civic": 4, "government": 4, "hospital": 3, "school": 3, "worship": 2, "shelter": 1, "sports": 1, "open_space": 0},
}

# Default OSM tags for Overpass queries
DEFAULT_OSM_TAGS = [
    "amenity=shelter",
    "building=bunker",
    "amenity=place_of_worship",
    "railway=station",
    "station=subway",
    "building=civic",
    "building=government",
    "building=school",
    "amenity=school",
    "building=hospital",
    "leisure=sports_centre",
]

# OSM tag → shelter type mapping
OSM_TAG_TO_SHELTER_TYPE: dict[str, str] = {
    "amenity=shelter": "shelter",
    "building=bunker": "bunker",
    "amenity=place_of_worship": "worship",
    "railway=station": "subway",
    "station=subway": "subway",
    "building=civic": "civic",
    "building=government": "government",
    "building=school": "school",
    "amenity=school": "school",
    "building=hospital": "hospital",
    "leisure=sports_centre": "sports",
}

# Travel modes
TRAVEL_MODES = ["walking", "driving"]

# Walking/driving speed estimates (m/s) for ETA calculation
TRAVEL_SPEEDS = {
    "walking": 1.4,   # ~5 km/h
    "driving": 8.3,   # ~30 km/h (urban average)
}
```

- [ ] **Step 3: Create __init__.py stub**

```python
"""Shelter Finder integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelter Finder from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
```

- [ ] **Step 4: Create hacs.json at repo root**

```json
{
  "name": "Shelter Finder",
  "render_readme": true,
  "homeassistant": "2024.1.0"
}
```

- [ ] **Step 5: Create tests/conftest.py**

```python
"""Fixtures for Shelter Finder tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    yield


@pytest.fixture
def mock_persons() -> list[str]:
    """Return test person entity IDs."""
    return ["person.alice", "person.bob"]


@pytest.fixture
def mock_config_entry_data(mock_persons: list[str]) -> dict:
    """Return mock config entry data."""
    return {
        "persons": mock_persons,
        "search_radius": 2000,
        "language": "fr",
        "enabled_threats": [
            "storm",
            "earthquake",
            "attack",
            "armed_conflict",
            "flood",
            "nuclear_chemical",
        ],
        "default_travel_mode": "walking",
        "webhook_id": "sf_test_webhook_id",
    }
```

- [ ] **Step 6: Create setup.cfg**

```ini
[tool:pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 7: Create requirements_test.txt**

```
pytest
pytest-asyncio
pytest-homeassistant-custom-component
pytest-cov
aiohttp
```

- [ ] **Step 8: Verify project structure**

Run: `find custom_components tests -type f | sort`

Expected:
```
custom_components/shelter_finder/__init__.py
custom_components/shelter_finder/const.py
custom_components/shelter_finder/manifest.json
tests/conftest.py
```

- [ ] **Step 9: Commit**

```bash
git add custom_components/ tests/ hacs.json requirements_test.txt setup.cfg
git commit -m "feat: scaffold project structure with manifest, constants, and test setup"
```

---

### Task 2: Cache Module

**Files:**
- Create: `custom_components/shelter_finder/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write failing tests for cache**

```python
"""Tests for Shelter Finder cache module."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.shelter_finder.cache import ShelterCache


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Return a temporary cache directory."""
    return tmp_path


@pytest.fixture
def cache(cache_dir: Path) -> ShelterCache:
    """Return a ShelterCache instance."""
    return ShelterCache(cache_dir, ttl_hours=1)


def test_save_and_load(cache: ShelterCache) -> None:
    """Test saving and loading shelter data."""
    shelters = [
        {"id": "1", "name": "Abri A", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker"},
        {"id": "2", "name": "Abri B", "latitude": 48.86, "longitude": 2.36, "shelter_type": "subway"},
    ]
    cache.save(shelters)
    loaded = cache.load()
    assert loaded == shelters


def test_load_empty_cache(cache: ShelterCache) -> None:
    """Test loading from an empty cache returns empty list."""
    assert cache.load() == []


def test_cache_expired(cache_dir: Path) -> None:
    """Test that expired cache returns empty list."""
    cache = ShelterCache(cache_dir, ttl_hours=0)  # 0 hours = always expired
    shelters = [{"id": "1", "name": "Test", "latitude": 0, "longitude": 0, "shelter_type": "shelter"}]
    cache.save(shelters)
    # Manually set mtime to the past
    cache_file = cache_dir / "shelter_finder_cache.json"
    old_time = time.time() - 7200  # 2 hours ago
    import os
    os.utime(cache_file, (old_time, old_time))
    assert cache.load() == []


def test_cache_not_expired(cache: ShelterCache) -> None:
    """Test that valid cache returns data."""
    shelters = [{"id": "1", "name": "Test", "latitude": 0, "longitude": 0, "shelter_type": "shelter"}]
    cache.save(shelters)
    loaded = cache.load()
    assert loaded == shelters


def test_is_valid_property(cache: ShelterCache) -> None:
    """Test is_valid property."""
    assert cache.is_valid is False
    cache.save([{"id": "1", "name": "Test", "latitude": 0, "longitude": 0, "shelter_type": "shelter"}])
    assert cache.is_valid is True


def test_corrupted_cache_returns_empty(cache: ShelterCache, cache_dir: Path) -> None:
    """Test that corrupted JSON returns empty list."""
    cache_file = cache_dir / "shelter_finder_cache.json"
    cache_file.write_text("not valid json{{{")
    assert cache.load() == []


def test_save_pois_and_load(cache: ShelterCache) -> None:
    """Test saving and loading custom POIs."""
    pois = [
        {"id": "poi1", "name": "Cave maison", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker"},
    ]
    cache.save_pois(pois)
    loaded = cache.load_pois()
    assert loaded == pois


def test_load_pois_empty(cache: ShelterCache) -> None:
    """Test loading POIs when none exist."""
    assert cache.load_pois() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.shelter_finder.cache'`

- [ ] **Step 3: Implement cache.py**

```python
"""Local file cache for shelter data."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

CACHE_FILENAME = "shelter_finder_cache.json"
POI_FILENAME = "shelter_finder_pois.json"


class ShelterCache:
    """File-based JSON cache with TTL for shelter data."""

    def __init__(self, storage_dir: Path, ttl_hours: int = 24) -> None:
        """Initialize the cache."""
        self._storage_dir = storage_dir
        self._ttl_seconds = ttl_hours * 3600
        self._cache_file = storage_dir / CACHE_FILENAME
        self._poi_file = storage_dir / POI_FILENAME

    @property
    def is_valid(self) -> bool:
        """Return True if cache exists and is not expired."""
        if not self._cache_file.exists():
            return False
        age = time.time() - self._cache_file.stat().st_mtime
        return age < self._ttl_seconds

    def save(self, shelters: list[dict[str, Any]]) -> None:
        """Save shelter data to cache file."""
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file.write_text(json.dumps(shelters, ensure_ascii=False), encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        """Load shelter data from cache. Returns empty list if expired or missing."""
        if not self.is_valid:
            return []
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            _LOGGER.warning("Cache file corrupted, returning empty")
            return []

    def save_pois(self, pois: list[dict[str, Any]]) -> None:
        """Save custom POIs to file."""
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._poi_file.write_text(json.dumps(pois, ensure_ascii=False), encoding="utf-8")

    def load_pois(self) -> list[dict[str, Any]]:
        """Load custom POIs. Returns empty list if missing."""
        if not self._poi_file.exists():
            return []
        try:
            data = json.loads(self._poi_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            _LOGGER.warning("POI file corrupted, returning empty")
            return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cache.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/cache.py tests/test_cache.py
git commit -m "feat: add file-based shelter cache with TTL and POI storage"
```

---

### Task 3: Overpass API Client

**Files:**
- Create: `custom_components/shelter_finder/overpass.py`
- Create: `tests/test_overpass.py`

- [ ] **Step 1: Write failing tests for Overpass client**

```python
"""Tests for Shelter Finder Overpass client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import ClientResponseError

from custom_components.shelter_finder.overpass import OverpassClient, build_overpass_query


SAMPLE_OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 123456,
            "lat": 48.8566,
            "lon": 2.3522,
            "tags": {
                "amenity": "shelter",
                "name": "Abri du Parc",
            },
        },
        {
            "type": "node",
            "id": 789012,
            "lat": 48.8600,
            "lon": 2.3400,
            "tags": {
                "building": "bunker",
                "name": "Bunker Souterrain",
            },
        },
        {
            "type": "way",
            "id": 345678,
            "center": {"lat": 48.8550, "lon": 2.3480},
            "tags": {
                "railway": "station",
                "name": "Gare du Nord",
            },
        },
    ],
}


def test_build_overpass_query() -> None:
    """Test Overpass QL query generation."""
    tags = ["amenity=shelter", "building=bunker"]
    query = build_overpass_query(48.85, 2.35, 2000, tags)
    assert "around:2000,48.85,2.35" in query
    assert 'node["amenity"="shelter"]' in query
    assert 'way["amenity"="shelter"]' in query
    assert 'node["building"="bunker"]' in query
    assert "[out:json]" in query
    assert "out center;" in query


def test_build_overpass_query_wildcard() -> None:
    """Test query with wildcard tag like shelter_type=*."""
    tags = ["shelter_type=*"]
    query = build_overpass_query(48.85, 2.35, 2000, tags)
    assert 'node["shelter_type"]' in query
    assert 'way["shelter_type"]' in query


@pytest.mark.asyncio
async def test_fetch_shelters_success() -> None:
    """Test successful shelter fetch."""
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=SAMPLE_OVERPASS_RESPONSE)
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    client = OverpassClient(session=mock_session)
    shelters = await client.fetch_shelters(48.85, 2.35, 2000)

    assert len(shelters) == 3
    assert shelters[0]["name"] == "Abri du Parc"
    assert shelters[0]["latitude"] == 48.8566
    assert shelters[0]["longitude"] == 2.3522
    assert shelters[0]["shelter_type"] == "shelter"
    assert shelters[0]["source"] == "osm"

    # Way element should use center coordinates
    assert shelters[2]["latitude"] == 48.8550
    assert shelters[2]["longitude"] == 2.3480


@pytest.mark.asyncio
async def test_fetch_shelters_empty_response() -> None:
    """Test fetch with no results."""
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"elements": []})
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    client = OverpassClient(session=mock_session)
    shelters = await client.fetch_shelters(48.85, 2.35, 2000)
    assert shelters == []


@pytest.mark.asyncio
async def test_fetch_shelters_api_error() -> None:
    """Test fetch with API error raises."""
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.raise_for_status = AsyncMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=AsyncMock(),
            history=(),
            status=429,
            message="Too Many Requests",
        )
    )
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    client = OverpassClient(session=mock_session)
    with pytest.raises(aiohttp.ClientResponseError):
        await client.fetch_shelters(48.85, 2.35, 2000)


def test_parse_element_node() -> None:
    """Test parsing a node element."""
    from custom_components.shelter_finder.overpass import _parse_element

    element = {
        "type": "node",
        "id": 123,
        "lat": 48.85,
        "lon": 2.35,
        "tags": {"amenity": "shelter", "name": "Test Shelter"},
    }
    result = _parse_element(element)
    assert result is not None
    assert result["osm_id"] == "node/123"
    assert result["name"] == "Test Shelter"
    assert result["latitude"] == 48.85
    assert result["longitude"] == 2.35
    assert result["shelter_type"] == "shelter"
    assert result["source"] == "osm"


def test_parse_element_no_name() -> None:
    """Test parsing element without name uses type as fallback."""
    from custom_components.shelter_finder.overpass import _parse_element

    element = {
        "type": "node",
        "id": 456,
        "lat": 48.86,
        "lon": 2.36,
        "tags": {"building": "bunker"},
    }
    result = _parse_element(element)
    assert result is not None
    assert result["name"] == "bunker"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_overpass.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement overpass.py**

```python
"""Overpass API client for fetching shelter data from OpenStreetMap."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import DEFAULT_OSM_TAGS, DEFAULT_OVERPASS_URL, OSM_TAG_TO_SHELTER_TYPE

_LOGGER = logging.getLogger(__name__)


def build_overpass_query(lat: float, lon: float, radius: int, tags: list[str]) -> str:
    """Build an Overpass QL query for shelters around a point."""
    union_parts = []
    for tag in tags:
        key, _, value = tag.partition("=")
        if value == "*" or value == "":
            filter_str = f'["{key}"]'
        else:
            filter_str = f'["{key}"="{value}"]'
        around = f"(around:{radius},{lat},{lon})"
        union_parts.append(f"  node{filter_str}{around};")
        union_parts.append(f"  way{filter_str}{around};")

    union_body = "\n".join(union_parts)
    return f"[out:json][timeout:25];\n(\n{union_body}\n);\nout center;"


def _determine_shelter_type(tags: dict[str, str]) -> str:
    """Determine shelter type from OSM tags."""
    for osm_tag, shelter_type in OSM_TAG_TO_SHELTER_TYPE.items():
        key, _, value = osm_tag.partition("=")
        if key in tags and (value == "*" or tags[key] == value):
            return shelter_type
    return "shelter"  # fallback


def _parse_element(element: dict[str, Any]) -> dict[str, Any] | None:
    """Parse an Overpass element into a shelter dict."""
    tags = element.get("tags", {})
    element_type = element.get("type", "node")
    element_id = element.get("id", 0)

    # Get coordinates
    if element_type == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    elif element_type == "way" and "center" in element:
        lat = element["center"].get("lat")
        lon = element["center"].get("lon")
    else:
        return None

    if lat is None or lon is None:
        return None

    shelter_type = _determine_shelter_type(tags)
    name = tags.get("name", shelter_type)

    return {
        "osm_id": f"{element_type}/{element_id}",
        "name": name,
        "latitude": lat,
        "longitude": lon,
        "shelter_type": shelter_type,
        "source": "osm",
        "address": tags.get("addr:street", ""),
    }


class OverpassClient:
    """Client for the Overpass API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str = DEFAULT_OVERPASS_URL,
        tags: list[str] | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._url = url
        self._tags = tags or DEFAULT_OSM_TAGS

    async def fetch_shelters(
        self,
        lat: float,
        lon: float,
        radius: int,
    ) -> list[dict[str, Any]]:
        """Fetch shelters from Overpass API around a point."""
        query = build_overpass_query(lat, lon, radius, self._tags)
        _LOGGER.debug("Overpass query: %s", query)

        async with self._session.post(self._url, data={"data": query}) as resp:
            resp.raise_for_status()
            data = await resp.json()

        elements = data.get("elements", [])
        shelters = []
        for element in elements:
            parsed = _parse_element(element)
            if parsed is not None:
                shelters.append(parsed)

        _LOGGER.info("Overpass returned %d shelters in %dm radius", len(shelters), radius)
        return shelters
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_overpass.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/overpass.py tests/test_overpass.py
git commit -m "feat: add Overpass API client with query builder and element parser"
```

---

### Task 4: Shelter Logic (Scoring, Ranking, Adaptive Radius)

**Files:**
- Create: `custom_components/shelter_finder/shelter_logic.py`
- Create: `tests/test_shelter_logic.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Shelter Finder shelter logic."""

from __future__ import annotations

import pytest

from custom_components.shelter_finder.shelter_logic import (
    compute_adaptive_radii,
    deduplicate_shelters,
    merge_shelters_and_pois,
    rank_shelters,
    score_shelter,
)


# --- score_shelter ---

def test_score_shelter_storm_bunker() -> None:
    """Bunker scores high for storm."""
    shelter = {"shelter_type": "bunker", "latitude": 48.85, "longitude": 2.35}
    score = score_shelter(shelter, "storm", distance_m=500)
    assert score > 0


def test_score_shelter_earthquake_open_space() -> None:
    """Open space scores highest for earthquake."""
    open_space = {"shelter_type": "open_space", "latitude": 48.85, "longitude": 2.35}
    bunker = {"shelter_type": "bunker", "latitude": 48.85, "longitude": 2.35}
    score_open = score_shelter(open_space, "earthquake", distance_m=500)
    score_bunker = score_shelter(bunker, "earthquake", distance_m=500)
    assert score_open > score_bunker


def test_score_shelter_closer_is_better() -> None:
    """Closer shelter scores higher than farther one of same type."""
    shelter = {"shelter_type": "bunker", "latitude": 48.85, "longitude": 2.35}
    score_close = score_shelter(shelter, "storm", distance_m=200)
    score_far = score_shelter(shelter, "storm", distance_m=5000)
    assert score_close > score_far


def test_score_shelter_unknown_type() -> None:
    """Unknown shelter type returns base distance score only."""
    shelter = {"shelter_type": "unknown_thing", "latitude": 48.85, "longitude": 2.35}
    score = score_shelter(shelter, "storm", distance_m=500)
    assert score >= 0


# --- rank_shelters ---

def test_rank_shelters() -> None:
    """Shelters are ranked by score descending."""
    shelters = [
        {"name": "Far bunker", "shelter_type": "bunker", "latitude": 48.85, "longitude": 2.35},
        {"name": "Close subway", "shelter_type": "subway", "latitude": 48.856, "longitude": 2.352},
    ]
    ranked = rank_shelters(shelters, "storm", person_lat=48.856, person_lon=2.352)
    # Close subway should rank higher because it's closer (distance advantage)
    # and subway scores 10 for storm
    assert ranked[0]["name"] == "Close subway"


def test_rank_shelters_empty() -> None:
    """Empty shelter list returns empty."""
    assert rank_shelters([], "storm", person_lat=48.85, person_lon=2.35) == []


# --- compute_adaptive_radii ---

def test_adaptive_radii_enough_results() -> None:
    """No expansion needed when enough results."""
    radii = compute_adaptive_radii(2000, 15000, found_count=5, min_results=3)
    assert radii == []  # No additional radii needed


def test_adaptive_radii_not_enough() -> None:
    """Returns expanded radii when not enough results."""
    radii = compute_adaptive_radii(2000, 15000, found_count=1, min_results=3)
    assert len(radii) > 0
    assert radii[0] == 5000  # 2000 * 2.5
    assert radii[1] == 10000  # 2000 * 5


def test_adaptive_radii_capped() -> None:
    """Expanded radii are capped at max."""
    radii = compute_adaptive_radii(5000, 15000, found_count=0, min_results=3)
    assert all(r <= 15000 for r in radii)


# --- deduplicate_shelters ---

def test_deduplicate_shelters_nearby() -> None:
    """Shelters within 50m are deduplicated, keeping the first."""
    shelters = [
        {"osm_id": "node/1", "name": "A", "latitude": 48.85000, "longitude": 2.35000, "source": "manual"},
        {"osm_id": "node/2", "name": "B", "latitude": 48.85001, "longitude": 2.35001, "source": "osm"},
    ]
    result = deduplicate_shelters(shelters, threshold_m=50)
    assert len(result) == 1
    assert result[0]["name"] == "A"


def test_deduplicate_shelters_far_apart() -> None:
    """Shelters far apart are both kept."""
    shelters = [
        {"osm_id": "node/1", "name": "A", "latitude": 48.85, "longitude": 2.35, "source": "osm"},
        {"osm_id": "node/2", "name": "B", "latitude": 48.86, "longitude": 2.36, "source": "osm"},
    ]
    result = deduplicate_shelters(shelters, threshold_m=50)
    assert len(result) == 2


# --- merge_shelters_and_pois ---

def test_merge_pois_first() -> None:
    """POIs come first, then OSM shelters, deduplicated."""
    osm = [
        {"osm_id": "node/1", "name": "OSM Shelter", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter", "source": "osm"},
    ]
    pois = [
        {"id": "poi1", "name": "Ma Cave", "latitude": 48.86, "longitude": 2.36, "shelter_type": "bunker", "source": "manual"},
    ]
    merged = merge_shelters_and_pois(osm, pois)
    assert len(merged) == 2
    assert merged[0]["source"] == "manual"  # POIs first


def test_merge_deduplicates() -> None:
    """POI near an OSM shelter: POI wins."""
    osm = [
        {"osm_id": "node/1", "name": "OSM Shelter", "latitude": 48.85000, "longitude": 2.35000, "shelter_type": "shelter", "source": "osm"},
    ]
    pois = [
        {"id": "poi1", "name": "Ma Cave", "latitude": 48.85001, "longitude": 2.35001, "shelter_type": "bunker", "source": "manual"},
    ]
    merged = merge_shelters_and_pois(osm, pois)
    assert len(merged) == 1
    assert merged[0]["name"] == "Ma Cave"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shelter_logic.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement shelter_logic.py**

```python
"""Shelter scoring, ranking, and adaptive radius logic."""

from __future__ import annotations

import math
from typing import Any

from .const import ADAPTIVE_RADIUS_MIN_RESULTS, THREAT_SHELTER_SCORES


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6_371_000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def score_shelter(
    shelter: dict[str, Any],
    threat_type: str,
    distance_m: float,
) -> float:
    """Score a shelter for a given threat type and distance.

    Score = type_score * 10 + distance_bonus
    - type_score: 0-10 from THREAT_SHELTER_SCORES
    - distance_bonus: 10 * (1 - distance/15000), clamped to [0, 10]
    """
    scores = THREAT_SHELTER_SCORES.get(threat_type, {})
    type_score = scores.get(shelter.get("shelter_type", ""), 0)
    distance_bonus = max(0.0, 10.0 * (1.0 - distance_m / 15000.0))
    return type_score * 10.0 + distance_bonus


def rank_shelters(
    shelters: list[dict[str, Any]],
    threat_type: str,
    person_lat: float,
    person_lon: float,
) -> list[dict[str, Any]]:
    """Rank shelters by score for a given threat and person position.

    Returns shelters sorted by score descending, with distance_m added.
    """
    scored = []
    for shelter in shelters:
        distance = _haversine_distance(
            person_lat, person_lon,
            shelter["latitude"], shelter["longitude"],
        )
        s = score_shelter(shelter, threat_type, distance)
        scored.append({**shelter, "distance_m": round(distance), "score": s})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def compute_adaptive_radii(
    base_radius: int,
    max_radius: int,
    found_count: int,
    min_results: int = ADAPTIVE_RADIUS_MIN_RESULTS,
) -> list[int]:
    """Return list of expanded radii to try if not enough results found.

    Returns empty list if found_count >= min_results.
    """
    if found_count >= min_results:
        return []

    expanded = []
    r1 = int(base_radius * 2.5)
    r2 = int(base_radius * 5)
    if r1 <= max_radius:
        expanded.append(r1)
    if r2 <= max_radius and r2 != r1:
        expanded.append(r2)
    return expanded


def deduplicate_shelters(
    shelters: list[dict[str, Any]],
    threshold_m: float = 50.0,
) -> list[dict[str, Any]]:
    """Remove duplicate shelters within threshold distance. First occurrence wins."""
    result: list[dict[str, Any]] = []
    for shelter in shelters:
        is_dup = False
        for existing in result:
            dist = _haversine_distance(
                shelter["latitude"], shelter["longitude"],
                existing["latitude"], existing["longitude"],
            )
            if dist < threshold_m:
                is_dup = True
                break
        if not is_dup:
            result.append(shelter)
    return result


def merge_shelters_and_pois(
    osm_shelters: list[dict[str, Any]],
    pois: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge POIs and OSM shelters. POIs come first and win deduplication."""
    combined = list(pois) + list(osm_shelters)
    return deduplicate_shelters(combined)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shelter_logic.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/shelter_logic.py tests/test_shelter_logic.py
git commit -m "feat: add shelter scoring, ranking, adaptive radius, and deduplication"
```

---

### Task 5: Routing Module (Haversine + ETA)

**Files:**
- Create: `custom_components/shelter_finder/routing.py`
- Create: `tests/test_routing.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Shelter Finder routing module."""

from __future__ import annotations

import pytest

from custom_components.shelter_finder.routing import (
    calculate_eta_minutes,
    haversine_distance,
)


def test_haversine_same_point() -> None:
    """Distance from a point to itself is 0."""
    assert haversine_distance(48.85, 2.35, 48.85, 2.35) == 0.0


def test_haversine_known_distance() -> None:
    """Paris to Versailles is approximately 14km."""
    dist = haversine_distance(48.8566, 2.3522, 48.8014, 2.1301)
    assert 14000 < dist < 18000


def test_haversine_short_distance() -> None:
    """Two nearby points in Paris."""
    dist = haversine_distance(48.8566, 2.3522, 48.8580, 2.3540)
    assert 100 < dist < 300


def test_eta_walking() -> None:
    """ETA for 1400m at walking speed (~5km/h) is ~16.7 minutes."""
    eta = calculate_eta_minutes(1400, "walking")
    assert 15 < eta < 18


def test_eta_driving() -> None:
    """ETA for 1400m at driving speed (~30km/h) is ~2.8 minutes."""
    eta = calculate_eta_minutes(1400, "driving")
    assert 2 < eta < 4


def test_eta_zero_distance() -> None:
    """Zero distance gives 0 ETA."""
    assert calculate_eta_minutes(0, "walking") == 0.0


def test_eta_unknown_mode_defaults_walking() -> None:
    """Unknown travel mode defaults to walking speed."""
    eta_unknown = calculate_eta_minutes(1400, "jetpack")
    eta_walking = calculate_eta_minutes(1400, "walking")
    assert eta_unknown == eta_walking
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routing.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement routing.py**

```python
"""Routing calculations for Shelter Finder."""

from __future__ import annotations

import math

from .const import TRAVEL_SPEEDS


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in meters."""
    R = 6_371_000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_eta_minutes(distance_m: float, travel_mode: str) -> float:
    """Calculate estimated time of arrival in minutes.

    Uses constant speed estimates from TRAVEL_SPEEDS.
    Falls back to walking speed for unknown modes.
    """
    if distance_m <= 0:
        return 0.0
    speed_ms = TRAVEL_SPEEDS.get(travel_mode, TRAVEL_SPEEDS["walking"])
    return round(distance_m / speed_ms / 60, 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routing.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/routing.py tests/test_routing.py
git commit -m "feat: add Haversine distance and ETA calculation"
```

---

### Task 6: ShelterUpdateCoordinator

**Files:**
- Create: `custom_components/shelter_finder/coordinator.py`
- Create: `tests/test_coordinator.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for ShelterUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.shelter_finder.coordinator import ShelterUpdateCoordinator


@pytest.fixture
def mock_cache() -> MagicMock:
    """Return a mock ShelterCache."""
    cache = MagicMock()
    cache.is_valid = False
    cache.load.return_value = []
    cache.load_pois.return_value = []
    cache.save = MagicMock()
    return cache


@pytest.fixture
def mock_overpass_client() -> AsyncMock:
    """Return a mock OverpassClient."""
    client = AsyncMock()
    client.fetch_shelters = AsyncMock(return_value=[
        {"osm_id": "node/1", "name": "Abri Test", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter", "source": "osm"},
    ])
    return client


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_cache: MagicMock,
    mock_overpass_client: AsyncMock,
) -> ShelterUpdateCoordinator:
    """Return a ShelterUpdateCoordinator with mocked dependencies."""
    coord = ShelterUpdateCoordinator(
        hass=hass,
        cache=mock_cache,
        overpass_client=mock_overpass_client,
        persons=["person.alice"],
        search_radius=2000,
        adaptive_radius=True,
        adaptive_radius_max=15000,
    )
    return coord


@pytest.mark.asyncio
async def test_first_refresh_fetches_from_overpass(
    coordinator: ShelterUpdateCoordinator,
    mock_overpass_client: AsyncMock,
    mock_cache: MagicMock,
) -> None:
    """First refresh with empty cache should call Overpass."""
    data = await coordinator._async_update_data()
    mock_overpass_client.fetch_shelters.assert_called_once()
    mock_cache.save.assert_called_once()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_refresh_uses_cache_when_valid(
    coordinator: ShelterUpdateCoordinator,
    mock_cache: MagicMock,
    mock_overpass_client: AsyncMock,
) -> None:
    """When cache is valid, don't call Overpass."""
    mock_cache.is_valid = True
    mock_cache.load.return_value = [
        {"osm_id": "node/1", "name": "Cached", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker", "source": "osm"},
    ]
    data = await coordinator._async_update_data()
    mock_overpass_client.fetch_shelters.assert_not_called()
    assert data[0]["name"] == "Cached"


@pytest.mark.asyncio
async def test_refresh_merges_pois(
    coordinator: ShelterUpdateCoordinator,
    mock_cache: MagicMock,
    mock_overpass_client: AsyncMock,
) -> None:
    """POIs are merged with OSM data."""
    mock_cache.load_pois.return_value = [
        {"id": "poi1", "name": "Ma Cave", "latitude": 48.86, "longitude": 2.36, "shelter_type": "bunker", "source": "manual"},
    ]
    data = await coordinator._async_update_data()
    assert len(data) == 2
    assert any(s["name"] == "Ma Cave" for s in data)


@pytest.mark.asyncio
async def test_overpass_error_raises_update_failed(
    coordinator: ShelterUpdateCoordinator,
    mock_overpass_client: AsyncMock,
) -> None:
    """Overpass API error with no cache raises UpdateFailed."""
    mock_overpass_client.fetch_shelters = AsyncMock(side_effect=Exception("API down"))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_overpass_error_fallback_to_cache(
    coordinator: ShelterUpdateCoordinator,
    mock_cache: MagicMock,
    mock_overpass_client: AsyncMock,
) -> None:
    """Overpass error with existing cache uses stale cache."""
    mock_cache.is_valid = False  # expired but file exists
    mock_cache.load.return_value = []
    # Simulate: cache file exists but is expired, however we can force-read
    stale_data = [{"osm_id": "node/1", "name": "Stale", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter", "source": "osm"}]
    mock_cache.load_stale.return_value = stale_data
    mock_overpass_client.fetch_shelters = AsyncMock(side_effect=Exception("API down"))

    data = await coordinator._async_update_data()
    assert data[0]["name"] == "Stale"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coordinator.py -v`
Expected: FAIL

- [ ] **Step 3: Add load_stale to cache.py**

Add this method to `ShelterCache` class in `cache.py`:

```python
    def load_stale(self) -> list[dict[str, Any]]:
        """Load cache data regardless of TTL. Returns empty if file missing or corrupted."""
        if not self._cache_file.exists():
            return []
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []
```

- [ ] **Step 4: Implement coordinator.py**

```python
"""DataUpdateCoordinator for Shelter Finder."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cache import ShelterCache
from .const import DOMAIN
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
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
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
        # Try cache first
        if self.cache.is_valid:
            shelters = self.cache.load()
            _LOGGER.debug("Using cached shelter data (%d shelters)", len(shelters))
        else:
            # Fetch from Overpass — use first person's position or home zone
            shelters = await self._fetch_from_overpass()

        # Merge with POIs
        pois = self.cache.load_pois()
        merged = merge_shelters_and_pois(shelters, pois)
        return merged

    async def _fetch_from_overpass(self) -> list[dict[str, Any]]:
        """Fetch shelters from Overpass, with adaptive radius and fallback."""
        # Use home zone as reference point for Overpass query
        home = self.hass.states.get("zone.home")
        if home is None:
            raise UpdateFailed("zone.home not found — cannot determine search center")

        lat = home.attributes.get("latitude", 0)
        lon = home.attributes.get("longitude", 0)

        try:
            shelters = await self.overpass_client.fetch_shelters(lat, lon, self.search_radius)

            # Adaptive radius: expand if not enough results
            if self.adaptive_radius:
                radii = compute_adaptive_radii(
                    self.search_radius,
                    self.adaptive_radius_max,
                    len(shelters),
                )
                for radius in radii:
                    extra = await self.overpass_client.fetch_shelters(lat, lon, radius)
                    shelters.extend(extra)
                    if len(shelters) >= 3:
                        break

            self.cache.save(shelters)
            return shelters

        except Exception as err:
            _LOGGER.warning("Overpass fetch failed: %s, trying stale cache", err)
            stale = self.cache.load_stale()
            if stale:
                return stale
            raise UpdateFailed(f"Overpass API error and no cached data: {err}") from err
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_coordinator.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/shelter_finder/coordinator.py custom_components/shelter_finder/cache.py tests/test_coordinator.py
git commit -m "feat: add ShelterUpdateCoordinator with Overpass polling, cache, and adaptive radius"
```

---

### Task 7: AlertCoordinator

**Files:**
- Create: `custom_components/shelter_finder/alert_coordinator.py`
- Create: `tests/test_alert_coordinator.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for AlertCoordinator."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.shelter_finder.alert_coordinator import AlertCoordinator


@pytest.fixture
def mock_shelter_coordinator() -> MagicMock:
    """Return mock ShelterUpdateCoordinator with data."""
    coord = MagicMock()
    coord.data = [
        {"osm_id": "node/1", "name": "Abri A", "latitude": 48.856, "longitude": 2.352, "shelter_type": "bunker", "source": "osm"},
        {"osm_id": "node/2", "name": "Abri B", "latitude": 48.860, "longitude": 2.340, "shelter_type": "subway", "source": "osm"},
    ]
    return coord


@pytest.fixture
def alert_coord(
    hass: HomeAssistant,
    mock_shelter_coordinator: MagicMock,
) -> AlertCoordinator:
    """Return an AlertCoordinator instance."""
    return AlertCoordinator(
        hass=hass,
        shelter_coordinator=mock_shelter_coordinator,
        persons=["person.alice", "person.bob"],
        travel_mode="walking",
        re_notification_interval=5,
        max_re_notifications=3,
    )


def test_initial_state(alert_coord: AlertCoordinator) -> None:
    """Alert is initially inactive."""
    assert alert_coord.is_active is False
    assert alert_coord.threat_type is None
    assert alert_coord.persons_safe == []


def test_trigger_alert(alert_coord: AlertCoordinator) -> None:
    """Triggering alert sets active state."""
    alert_coord.trigger("storm", triggered_by="manual")
    assert alert_coord.is_active is True
    assert alert_coord.threat_type == "storm"
    assert alert_coord.triggered_by == "manual"
    assert alert_coord.triggered_at is not None


def test_cancel_alert(alert_coord: AlertCoordinator) -> None:
    """Cancelling alert resets state."""
    alert_coord.trigger("storm", triggered_by="manual")
    alert_coord.cancel()
    assert alert_coord.is_active is False
    assert alert_coord.threat_type is None
    assert alert_coord.persons_safe == []


def test_confirm_safe(alert_coord: AlertCoordinator) -> None:
    """Confirming a person adds them to safe list."""
    alert_coord.trigger("storm", triggered_by="manual")
    alert_coord.confirm_safe("person.alice")
    assert "person.alice" in alert_coord.persons_safe


def test_confirm_safe_no_duplicate(alert_coord: AlertCoordinator) -> None:
    """Confirming same person twice doesn't duplicate."""
    alert_coord.trigger("storm", triggered_by="manual")
    alert_coord.confirm_safe("person.alice")
    alert_coord.confirm_safe("person.alice")
    assert alert_coord.persons_safe.count("person.alice") == 1


def test_confirm_safe_when_no_alert(alert_coord: AlertCoordinator) -> None:
    """Confirming when no alert is active does nothing."""
    alert_coord.confirm_safe("person.alice")
    assert alert_coord.persons_safe == []


def test_all_safe_property(alert_coord: AlertCoordinator) -> None:
    """all_safe is True only when all persons confirmed."""
    alert_coord.trigger("storm", triggered_by="manual")
    assert alert_coord.all_safe is False
    alert_coord.confirm_safe("person.alice")
    assert alert_coord.all_safe is False
    alert_coord.confirm_safe("person.bob")
    assert alert_coord.all_safe is True


def test_get_best_shelter_for_person(alert_coord: AlertCoordinator, hass: HomeAssistant) -> None:
    """Get best shelter computes ranking for a person position."""
    # Mock person state with GPS attributes
    mock_state = MagicMock()
    mock_state.attributes = {"latitude": 48.857, "longitude": 2.351}
    hass.states._states = {"person.alice": mock_state}

    with patch.object(hass.states, "get", return_value=mock_state):
        result = alert_coord.get_best_shelter("person.alice")

    assert result is not None
    assert "name" in result
    assert "distance_m" in result
    assert "score" in result


def test_trigger_invalid_threat_type(alert_coord: AlertCoordinator) -> None:
    """Triggering with invalid threat type raises ValueError."""
    with pytest.raises(ValueError, match="Unknown threat type"):
        alert_coord.trigger("zombie_apocalypse", triggered_by="manual")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_alert_coordinator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement alert_coordinator.py**

```python
"""Alert coordinator for Shelter Finder."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant

from .const import THREAT_TYPES, TRAVEL_SPEEDS
from .routing import calculate_eta_minutes, haversine_distance
from .shelter_logic import rank_shelters

_LOGGER = logging.getLogger(__name__)


class AlertCoordinator:
    """Manages alert state and shelter recommendations."""

    def __init__(
        self,
        hass: HomeAssistant,
        shelter_coordinator: Any,
        persons: list[str],
        travel_mode: str = "walking",
        re_notification_interval: int = 5,
        max_re_notifications: int = 3,
    ) -> None:
        """Initialize the alert coordinator."""
        self.hass = hass
        self.shelter_coordinator = shelter_coordinator
        self.persons = persons
        self.travel_mode = travel_mode
        self.re_notification_interval = re_notification_interval
        self.max_re_notifications = max_re_notifications

        # Alert state
        self._is_active = False
        self._threat_type: str | None = None
        self._triggered_by: str | None = None
        self._triggered_at: datetime | None = None
        self._persons_safe: list[str] = []
        self._notification_counts: dict[str, int] = {}

    @property
    def is_active(self) -> bool:
        """Return whether an alert is currently active."""
        return self._is_active

    @property
    def threat_type(self) -> str | None:
        """Return the current threat type."""
        return self._threat_type

    @property
    def triggered_by(self) -> str | None:
        """Return who/what triggered the alert."""
        return self._triggered_by

    @property
    def triggered_at(self) -> datetime | None:
        """Return when the alert was triggered."""
        return self._triggered_at

    @property
    def persons_safe(self) -> list[str]:
        """Return list of persons who confirmed safe."""
        return list(self._persons_safe)

    @property
    def all_safe(self) -> bool:
        """Return True if all tracked persons are confirmed safe."""
        if not self._is_active:
            return False
        return all(p in self._persons_safe for p in self.persons)

    def trigger(self, threat_type: str, triggered_by: str = "manual") -> None:
        """Trigger an alert."""
        if threat_type not in THREAT_TYPES:
            raise ValueError(f"Unknown threat type: {threat_type}")

        self._is_active = True
        self._threat_type = threat_type
        self._triggered_by = triggered_by
        self._triggered_at = datetime.now(timezone.utc)
        self._persons_safe = []
        self._notification_counts = {p: 0 for p in self.persons}
        _LOGGER.warning("Alert triggered: %s by %s", threat_type, triggered_by)

    def cancel(self) -> None:
        """Cancel the current alert."""
        self._is_active = False
        self._threat_type = None
        self._triggered_by = None
        self._triggered_at = None
        self._persons_safe = []
        self._notification_counts = {}
        _LOGGER.info("Alert cancelled")

    def confirm_safe(self, person_entity_id: str) -> None:
        """Mark a person as safe."""
        if not self._is_active:
            return
        if person_entity_id not in self._persons_safe:
            self._persons_safe.append(person_entity_id)
            _LOGGER.info("Person confirmed safe: %s", person_entity_id)

    def get_best_shelter(self, person_entity_id: str) -> dict[str, Any] | None:
        """Get the best shelter recommendation for a person."""
        if not self._is_active or self._threat_type is None:
            return None

        state = self.hass.states.get(person_entity_id)
        if state is None:
            return None

        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is None or lon is None:
            return None

        shelters = self.shelter_coordinator.data or []
        ranked = rank_shelters(shelters, self._threat_type, lat, lon)

        if not ranked:
            return None

        best = ranked[0]
        best["eta_minutes"] = calculate_eta_minutes(best["distance_m"], self.travel_mode)
        return best

    def should_re_notify(self, person_entity_id: str) -> bool:
        """Check if a person should receive a re-notification."""
        if not self._is_active:
            return False
        if person_entity_id in self._persons_safe:
            return False
        count = self._notification_counts.get(person_entity_id, 0)
        return count < self.max_re_notifications

    def record_notification(self, person_entity_id: str) -> None:
        """Record that a notification was sent to a person."""
        self._notification_counts[person_entity_id] = (
            self._notification_counts.get(person_entity_id, 0) + 1
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_alert_coordinator.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/alert_coordinator.py tests/test_alert_coordinator.py
git commit -m "feat: add AlertCoordinator with trigger, cancel, confirm, and shelter ranking"
```

---

### Task 8: Config Flow and Translations

**Files:**
- Create: `custom_components/shelter_finder/config_flow.py`
- Create: `custom_components/shelter_finder/strings.json`
- Create: `custom_components/shelter_finder/translations/en.json`
- Create: `custom_components/shelter_finder/translations/fr.json`
- Create: `tests/test_config_flow.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Shelter Finder config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.shelter_finder.const import DOMAIN


@pytest.fixture
def mock_person_states(hass: HomeAssistant) -> None:
    """Set up mock person entities in hass."""
    hass.states.async_set("person.alice", "home", {"friendly_name": "Alice"})
    hass.states.async_set("person.bob", "away", {"friendly_name": "Bob"})


async def test_full_config_flow(hass: HomeAssistant, mock_person_states: None) -> None:
    """Test complete config flow from step 1 to step 2."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Step 1: select persons and radius
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "persons": ["person.alice", "person.bob"],
            "search_radius": 3000,
            "language": "fr",
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "threats"

    # Step 2: select threats and travel mode
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            "enabled_threats": ["storm", "earthquake", "attack"],
            "default_travel_mode": "walking",
        },
    )
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Shelter Finder"
    assert result3["data"]["persons"] == ["person.alice", "person.bob"]
    assert result3["data"]["search_radius"] == 3000
    assert result3["data"]["enabled_threats"] == ["storm", "earthquake", "attack"]


async def test_config_flow_default_values(hass: HomeAssistant, mock_person_states: None) -> None:
    """Test that config flow has correct defaults."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    schema = result["data_schema"].schema
    # Verify search_radius has default
    for key, val in schema.items():
        if str(key) == "search_radius":
            assert key.default() == 2000


async def test_single_instance(hass: HomeAssistant, mock_person_states: None) -> None:
    """Test only one instance can be configured."""
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"persons": ["person.alice"], "search_radius": 2000, "language": "fr"},
    )
    await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"enabled_threats": ["storm"], "default_travel_mode": "walking"},
    )

    # Try second instance
    result_dup = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_dup["type"] == FlowResultType.ABORT
    assert result_dup["reason"] == "single_instance_allowed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_flow.py -v`
Expected: FAIL

- [ ] **Step 3: Implement config_flow.py**

```python
"""Config flow for Shelter Finder."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ADAPTIVE_RADIUS,
    CONF_ADAPTIVE_RADIUS_MAX,
    CONF_CACHE_TTL,
    CONF_CUSTOM_OSM_TAGS,
    CONF_DEFAULT_TRAVEL_MODE,
    CONF_ENABLED_THREATS,
    CONF_LANGUAGE,
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_OSRM_ENABLED,
    CONF_OSRM_URL,
    CONF_OVERPASS_URL,
    CONF_PERSONS,
    CONF_RE_NOTIFICATION_INTERVAL,
    CONF_SEARCH_RADIUS,
    CONF_WEBHOOK_ID,
    DEFAULT_ADAPTIVE_RADIUS_MAX,
    DEFAULT_CACHE_TTL,
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_RE_NOTIFICATIONS,
    DEFAULT_OVERPASS_URL,
    DEFAULT_RADIUS,
    DEFAULT_RE_NOTIFICATION_INTERVAL,
    DEFAULT_TRAVEL_MODE,
    DOMAIN,
    THREAT_TYPES,
    TRAVEL_MODES,
)


class ShelterFinderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shelter Finder."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._user_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step 1: persons, radius, language."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._user_input.update(user_input)
            return await self.async_step_threats()

        # Get available person entities
        person_entities = [
            state.entity_id
            for state in self.hass.states.async_all("person")
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSONS, default=person_entities): vol.All(
                        vol.Coerce(list), [vol.In(person_entities)]
                    ),
                    vol.Required(CONF_SEARCH_RADIUS, default=DEFAULT_RADIUS): vol.All(
                        int, vol.Range(min=500, max=50000)
                    ),
                    vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
                        ["fr", "en"]
                    ),
                }
            ),
        )

    async def async_step_threats(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step 2: threats and travel mode."""
        if user_input is not None:
            self._user_input.update(user_input)
            self._user_input[CONF_WEBHOOK_ID] = f"sf_{uuid.uuid4().hex[:12]}"
            return self.async_create_entry(
                title="Shelter Finder",
                data=self._user_input,
            )

        return self.async_show_form(
            step_id="threats",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLED_THREATS, default=THREAT_TYPES
                    ): vol.All(vol.Coerce(list), [vol.In(THREAT_TYPES)]),
                    vol.Required(
                        CONF_DEFAULT_TRAVEL_MODE, default=DEFAULT_TRAVEL_MODE
                    ): vol.In(TRAVEL_MODES),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return ShelterFinderOptionsFlow(config_entry)


class ShelterFinderOptionsFlow(OptionsFlow):
    """Handle options for Shelter Finder."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options or self._config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SEARCH_RADIUS,
                        default=current.get(CONF_SEARCH_RADIUS, DEFAULT_RADIUS),
                    ): int,
                    vol.Required(
                        CONF_DEFAULT_TRAVEL_MODE,
                        default=current.get(CONF_DEFAULT_TRAVEL_MODE, DEFAULT_TRAVEL_MODE),
                    ): vol.In(TRAVEL_MODES),
                    vol.Required(
                        CONF_OVERPASS_URL,
                        default=current.get(CONF_OVERPASS_URL, DEFAULT_OVERPASS_URL),
                    ): str,
                    vol.Required(
                        CONF_CACHE_TTL,
                        default=current.get(CONF_CACHE_TTL, DEFAULT_CACHE_TTL),
                    ): int,
                    vol.Required(
                        CONF_ADAPTIVE_RADIUS,
                        default=current.get(CONF_ADAPTIVE_RADIUS, True),
                    ): bool,
                    vol.Required(
                        CONF_RE_NOTIFICATION_INTERVAL,
                        default=current.get(CONF_RE_NOTIFICATION_INTERVAL, DEFAULT_RE_NOTIFICATION_INTERVAL),
                    ): int,
                    vol.Required(
                        CONF_MAX_RE_NOTIFICATIONS,
                        default=current.get(CONF_MAX_RE_NOTIFICATIONS, DEFAULT_MAX_RE_NOTIFICATIONS),
                    ): int,
                }
            ),
        )
```

- [ ] **Step 4: Create strings.json**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Shelter Finder Setup",
        "description": "Select the people to track and the search radius for shelters.",
        "data": {
          "persons": "People to track",
          "search_radius": "Search radius (meters)",
          "language": "Language"
        }
      },
      "threats": {
        "title": "Threat Configuration",
        "description": "Select which threat types to enable and the default travel mode.",
        "data": {
          "enabled_threats": "Enabled threats",
          "default_travel_mode": "Default travel mode"
        }
      }
    },
    "abort": {
      "single_instance_allowed": "Only one Shelter Finder instance is allowed."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Shelter Finder Options",
        "data": {
          "search_radius": "Search radius (meters)",
          "default_travel_mode": "Default travel mode",
          "overpass_url": "Overpass API URL",
          "cache_ttl": "Cache duration (hours)",
          "adaptive_radius": "Adaptive search radius",
          "re_notification_interval": "Re-notification interval (minutes)",
          "max_re_notifications": "Maximum re-notifications"
        }
      }
    }
  }
}
```

- [ ] **Step 5: Create translations/en.json** (same content as strings.json)

Copy `strings.json` content to `translations/en.json`.

- [ ] **Step 6: Create translations/fr.json**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Configuration Shelter Finder",
        "description": "Sélectionnez les personnes à suivre et le rayon de recherche des abris.",
        "data": {
          "persons": "Personnes à suivre",
          "search_radius": "Rayon de recherche (mètres)",
          "language": "Langue"
        }
      },
      "threats": {
        "title": "Configuration des menaces",
        "description": "Sélectionnez les types de menaces à activer et le mode de déplacement par défaut.",
        "data": {
          "enabled_threats": "Menaces activées",
          "default_travel_mode": "Mode de déplacement par défaut"
        }
      }
    },
    "abort": {
      "single_instance_allowed": "Une seule instance de Shelter Finder est autorisée."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Options Shelter Finder",
        "data": {
          "search_radius": "Rayon de recherche (mètres)",
          "default_travel_mode": "Mode de déplacement par défaut",
          "overpass_url": "URL de l'API Overpass",
          "cache_ttl": "Durée du cache (heures)",
          "adaptive_radius": "Rayon de recherche adaptatif",
          "re_notification_interval": "Intervalle de re-notification (minutes)",
          "max_re_notifications": "Nombre maximum de re-notifications"
        }
      }
    }
  }
}
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_config_flow.py -v`
Expected: All 3 tests PASS

- [ ] **Step 8: Commit**

```bash
git add custom_components/shelter_finder/config_flow.py custom_components/shelter_finder/strings.json custom_components/shelter_finder/translations/ tests/test_config_flow.py
git commit -m "feat: add 2-step config flow with options and fr/en translations"
```

---

### Task 9: Sensor Entities

**Files:**
- Create: `custom_components/shelter_finder/sensor.py`
- Create: `tests/test_sensor.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Shelter Finder sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.shelter_finder.sensor import (
    ShelterAlertTypeSensor,
    ShelterDistanceSensor,
    ShelterETASensor,
    ShelterNearestSensor,
)


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Return mock coordinator with shelter data."""
    coord = MagicMock()
    coord.data = [
        {"osm_id": "node/1", "name": "Abri Test", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker", "source": "osm"},
    ]
    return coord


@pytest.fixture
def mock_alert_coordinator() -> MagicMock:
    """Return mock alert coordinator."""
    alert = MagicMock()
    alert.is_active = False
    alert.threat_type = None
    alert.get_best_shelter.return_value = None
    return alert


def test_nearest_sensor_attributes(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Test ShelterNearestSensor has correct attributes."""
    sensor = ShelterNearestSensor(
        coordinator=mock_coordinator,
        alert_coordinator=mock_alert_coordinator,
        person_id="person.alice",
        person_name="alice",
    )
    assert sensor.unique_id == "shelter_finder_alice_nearest"
    assert sensor.name == "alice shelter nearest"
    assert sensor.icon == "mdi:shield-home"


def test_distance_sensor_unit(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Test ShelterDistanceSensor has meter unit."""
    sensor = ShelterDistanceSensor(
        coordinator=mock_coordinator,
        alert_coordinator=mock_alert_coordinator,
        person_id="person.alice",
        person_name="alice",
    )
    assert sensor.native_unit_of_measurement == "m"


def test_eta_sensor_unit(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Test ShelterETASensor has minute unit."""
    sensor = ShelterETASensor(
        coordinator=mock_coordinator,
        alert_coordinator=mock_alert_coordinator,
        person_id="person.alice",
        person_name="alice",
    )
    assert sensor.native_unit_of_measurement == "min"


def test_alert_type_sensor_no_alert(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Alert type sensor shows 'none' when no alert."""
    sensor = ShelterAlertTypeSensor(
        coordinator=mock_coordinator,
        alert_coordinator=mock_alert_coordinator,
    )
    assert sensor.native_value == "none"


def test_alert_type_sensor_active(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Alert type sensor shows threat type when alert active."""
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.threat_type = "storm"
    sensor = ShelterAlertTypeSensor(
        coordinator=mock_coordinator,
        alert_coordinator=mock_alert_coordinator,
    )
    assert sensor.native_value == "storm"


def test_nearest_sensor_with_alert(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Nearest sensor shows best shelter during alert."""
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.get_best_shelter.return_value = {
        "name": "Best Bunker",
        "latitude": 48.856,
        "longitude": 2.352,
        "shelter_type": "bunker",
        "distance_m": 450,
        "eta_minutes": 5.4,
        "source": "osm",
        "score": 95.0,
    }
    sensor = ShelterNearestSensor(
        coordinator=mock_coordinator,
        alert_coordinator=mock_alert_coordinator,
        person_id="person.alice",
        person_name="alice",
    )
    assert sensor.native_value == "Best Bunker"
    attrs = sensor.extra_state_attributes
    assert attrs["shelter_type"] == "bunker"
    assert attrs["distance_m"] == 450
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sensor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement sensor.py**

```python
"""Sensor platform for Shelter Finder."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .alert_coordinator import AlertCoordinator
from .const import CONF_PERSONS, DOMAIN
from .coordinator import ShelterUpdateCoordinator
from .routing import calculate_eta_minutes, haversine_distance


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shelter Finder sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ShelterUpdateCoordinator = data["coordinator"]
    alert_coordinator: AlertCoordinator = data["alert_coordinator"]
    persons = entry.data.get(CONF_PERSONS, [])

    entities: list[SensorEntity] = []
    for person_id in persons:
        person_name = person_id.split(".")[-1]
        entities.append(ShelterNearestSensor(coordinator, alert_coordinator, person_id, person_name))
        entities.append(ShelterDistanceSensor(coordinator, alert_coordinator, person_id, person_name))
        entities.append(ShelterETASensor(coordinator, alert_coordinator, person_id, person_name))

    entities.append(ShelterAlertTypeSensor(coordinator, alert_coordinator))
    async_add_entities(entities)


class ShelterNearestSensor(CoordinatorEntity[ShelterUpdateCoordinator], SensorEntity):
    """Sensor showing the nearest/best shelter for a person."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-home"

    def __init__(
        self,
        coordinator: ShelterUpdateCoordinator,
        alert_coordinator: AlertCoordinator,
        person_id: str,
        person_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_nearest"
        self._attr_name = f"{person_name} shelter nearest"
        self._best_shelter: dict[str, Any] | None = None

    @property
    def native_value(self) -> str | None:
        """Return shelter name."""
        shelter = self._get_shelter()
        return shelter["name"] if shelter else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return shelter details as attributes."""
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
        """Get best shelter from alert coordinator or compute from cache."""
        if self._alert_coordinator.is_active:
            return self._alert_coordinator.get_best_shelter(self._person_id)

        # In standby: find nearest from cache using person position
        state = self.hass.states.get(self._person_id) if self.hass else None
        if state is None:
            return None
        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is None or lon is None or not self.coordinator.data:
            return None

        # Simple nearest by distance
        nearest = None
        min_dist = float("inf")
        for shelter in self.coordinator.data:
            dist = haversine_distance(lat, lon, shelter["latitude"], shelter["longitude"])
            if dist < min_dist:
                min_dist = dist
                nearest = {**shelter, "distance_m": round(dist)}
        return nearest


class ShelterDistanceSensor(CoordinatorEntity[ShelterUpdateCoordinator], SensorEntity):
    """Sensor showing distance to nearest shelter."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:map-marker-distance"

    def __init__(
        self,
        coordinator: ShelterUpdateCoordinator,
        alert_coordinator: AlertCoordinator,
        person_id: str,
        person_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_distance"
        self._attr_name = f"{person_name} shelter distance"

    @property
    def native_value(self) -> int | None:
        """Return distance in meters."""
        if self._alert_coordinator.is_active:
            shelter = self._alert_coordinator.get_best_shelter(self._person_id)
            return shelter["distance_m"] if shelter else None
        return None


class ShelterETASensor(CoordinatorEntity[ShelterUpdateCoordinator], SensorEntity):
    """Sensor showing ETA to nearest shelter."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:clock-fast"

    def __init__(
        self,
        coordinator: ShelterUpdateCoordinator,
        alert_coordinator: AlertCoordinator,
        person_id: str,
        person_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_eta"
        self._attr_name = f"{person_name} shelter ETA"

    @property
    def native_value(self) -> float | None:
        """Return ETA in minutes."""
        if self._alert_coordinator.is_active:
            shelter = self._alert_coordinator.get_best_shelter(self._person_id)
            return shelter.get("eta_minutes") if shelter else None
        return None


class ShelterAlertTypeSensor(CoordinatorEntity[ShelterUpdateCoordinator], SensorEntity):
    """Sensor showing the current alert threat type."""

    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_alert_type"
    _attr_name = "Alert type"
    _attr_icon = "mdi:alert"

    def __init__(
        self,
        coordinator: ShelterUpdateCoordinator,
        alert_coordinator: AlertCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator

    @property
    def native_value(self) -> str:
        """Return current threat type or 'none'."""
        if self._alert_coordinator.is_active and self._alert_coordinator.threat_type:
            return self._alert_coordinator.threat_type
        return "none"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sensor.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/sensor.py tests/test_sensor.py
git commit -m "feat: add sensor entities (nearest, distance, ETA, alert type)"
```

---

### Task 10: Binary Sensor

**Files:**
- Create: `custom_components/shelter_finder/binary_sensor.py`
- Create: `tests/test_binary_sensor.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Shelter Finder binary sensor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.shelter_finder.binary_sensor import ShelterAlertBinarySensor


@pytest.fixture
def mock_coordinator() -> MagicMock:
    coord = MagicMock()
    coord.data = []
    return coord


@pytest.fixture
def mock_alert_coordinator() -> MagicMock:
    alert = MagicMock()
    alert.is_active = False
    alert.threat_type = None
    alert.triggered_at = None
    alert.triggered_by = None
    alert.persons_safe = []
    return alert


def test_binary_sensor_off(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Binary sensor is off when no alert."""
    sensor = ShelterAlertBinarySensor(mock_coordinator, mock_alert_coordinator)
    assert sensor.is_on is False
    assert sensor.unique_id == "shelter_finder_alert"


def test_binary_sensor_on(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Binary sensor is on during alert."""
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.threat_type = "storm"
    mock_alert_coordinator.triggered_by = "webhook"
    sensor = ShelterAlertBinarySensor(mock_coordinator, mock_alert_coordinator)
    assert sensor.is_on is True


def test_binary_sensor_attributes(mock_coordinator: MagicMock, mock_alert_coordinator: MagicMock) -> None:
    """Extra attributes include threat details."""
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.threat_type = "attack"
    mock_alert_coordinator.triggered_by = "manual"
    mock_alert_coordinator.persons_safe = ["person.alice"]
    sensor = ShelterAlertBinarySensor(mock_coordinator, mock_alert_coordinator)
    attrs = sensor.extra_state_attributes
    assert attrs["threat_type"] == "attack"
    assert attrs["triggered_by"] == "manual"
    assert attrs["persons_safe"] == ["person.alice"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_binary_sensor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement binary_sensor.py**

```python
"""Binary sensor platform for Shelter Finder."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .alert_coordinator import AlertCoordinator
from .const import DOMAIN
from .coordinator import ShelterUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shelter Finder binary sensor."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ShelterUpdateCoordinator = data["coordinator"]
    alert_coordinator: AlertCoordinator = data["alert_coordinator"]
    async_add_entities([ShelterAlertBinarySensor(coordinator, alert_coordinator)])


class ShelterAlertBinarySensor(
    CoordinatorEntity[ShelterUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether an alert is active."""

    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_alert"
    _attr_name = "Alert"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:alarm-light"

    def __init__(
        self,
        coordinator: ShelterUpdateCoordinator,
        alert_coordinator: AlertCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator

    @property
    def is_on(self) -> bool:
        """Return True if an alert is active."""
        return self._alert_coordinator.is_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return alert details."""
        ac = self._alert_coordinator
        return {
            "threat_type": ac.threat_type,
            "triggered_at": str(ac.triggered_at) if ac.triggered_at else None,
            "triggered_by": ac.triggered_by,
            "persons_safe": ac.persons_safe,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_binary_sensor.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/binary_sensor.py tests/test_binary_sensor.py
git commit -m "feat: add alert binary sensor"
```

---

### Task 11: Button Entities

**Files:**
- Create: `custom_components/shelter_finder/button.py`
- Create: `tests/test_button.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Shelter Finder button entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.shelter_finder.button import (
    ShelterCancelAlertButton,
    ShelterTriggerAlertButton,
)


@pytest.fixture
def mock_alert_coordinator() -> MagicMock:
    alert = MagicMock()
    alert.trigger = MagicMock()
    alert.cancel = MagicMock()
    alert.is_active = False
    return alert


def test_trigger_button_attributes(mock_alert_coordinator: MagicMock) -> None:
    """Trigger button has correct metadata."""
    button = ShelterTriggerAlertButton(mock_alert_coordinator)
    assert button.unique_id == "shelter_finder_trigger_alert"
    assert "alert" in button.icon


def test_cancel_button_attributes(mock_alert_coordinator: MagicMock) -> None:
    """Cancel button has correct metadata."""
    button = ShelterCancelAlertButton(mock_alert_coordinator)
    assert button.unique_id == "shelter_finder_cancel_alert"


@pytest.mark.asyncio
async def test_trigger_button_press(mock_alert_coordinator: MagicMock) -> None:
    """Pressing trigger button triggers alert with default storm type."""
    button = ShelterTriggerAlertButton(mock_alert_coordinator)
    await button.async_press()
    mock_alert_coordinator.trigger.assert_called_once_with("storm", triggered_by="button")


@pytest.mark.asyncio
async def test_cancel_button_press(mock_alert_coordinator: MagicMock) -> None:
    """Pressing cancel button cancels alert."""
    button = ShelterCancelAlertButton(mock_alert_coordinator)
    await button.async_press()
    mock_alert_coordinator.cancel.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_button.py -v`
Expected: FAIL

- [ ] **Step 3: Implement button.py**

```python
"""Button platform for Shelter Finder."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .alert_coordinator import AlertCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shelter Finder buttons."""
    alert_coordinator: AlertCoordinator = hass.data[DOMAIN][entry.entry_id]["alert_coordinator"]
    async_add_entities([
        ShelterTriggerAlertButton(alert_coordinator),
        ShelterCancelAlertButton(alert_coordinator),
    ])


class ShelterTriggerAlertButton(ButtonEntity):
    """Button to trigger an alert."""

    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_trigger_alert"
    _attr_name = "Trigger alert"
    _attr_icon = "mdi:alert-plus"

    def __init__(self, alert_coordinator: AlertCoordinator) -> None:
        """Initialize."""
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        """Handle button press — trigger alert with default type."""
        self._alert_coordinator.trigger("storm", triggered_by="button")


class ShelterCancelAlertButton(ButtonEntity):
    """Button to cancel an active alert."""

    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_cancel_alert"
    _attr_name = "Cancel alert"
    _attr_icon = "mdi:alert-remove"

    def __init__(self, alert_coordinator: AlertCoordinator) -> None:
        """Initialize."""
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        """Handle button press — cancel the current alert."""
        self._alert_coordinator.cancel()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_button.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/button.py tests/test_button.py
git commit -m "feat: add trigger and cancel alert buttons"
```

---

### Task 12: Webhook Handler

**Files:**
- Create: `custom_components/shelter_finder/webhook.py`
- Create: `tests/test_webhook.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Shelter Finder webhook handler."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from custom_components.shelter_finder.webhook import async_handle_webhook
from custom_components.shelter_finder.const import THREAT_TYPES


@pytest.fixture
def mock_hass() -> MagicMock:
    hass = MagicMock()
    alert_coord = MagicMock()
    alert_coord.trigger = MagicMock()
    hass.data = {"shelter_finder": {"alert_coordinator": alert_coord}}
    return hass


@pytest.mark.asyncio
async def test_webhook_valid_payload(mock_hass: MagicMock) -> None:
    """Valid webhook triggers alert."""
    request = make_mocked_request("POST", "/api/webhook/test")
    request._payload = json.dumps({"threat_type": "storm", "source": "fr-alert"}).encode()
    request.json = lambda: json.loads(request._payload)

    response = await async_handle_webhook(mock_hass, "test", request)
    assert response.status == 200
    mock_hass.data["shelter_finder"]["alert_coordinator"].trigger.assert_called_once_with(
        "storm", triggered_by="webhook:fr-alert"
    )


@pytest.mark.asyncio
async def test_webhook_invalid_threat_type(mock_hass: MagicMock) -> None:
    """Invalid threat type returns 400."""
    request = make_mocked_request("POST", "/api/webhook/test")
    request.json = lambda: {"threat_type": "zombie"}

    response = await async_handle_webhook(mock_hass, "test", request)
    assert response.status == 400


@pytest.mark.asyncio
async def test_webhook_missing_threat_type(mock_hass: MagicMock) -> None:
    """Missing threat_type returns 400."""
    request = make_mocked_request("POST", "/api/webhook/test")
    request.json = lambda: {"message": "test"}

    response = await async_handle_webhook(mock_hass, "test", request)
    assert response.status == 400


@pytest.mark.asyncio
async def test_webhook_with_optional_message(mock_hass: MagicMock) -> None:
    """Webhook with optional message passes it through."""
    request = make_mocked_request("POST", "/api/webhook/test")
    request.json = lambda: {"threat_type": "attack", "message": "Alerte attentat"}

    response = await async_handle_webhook(mock_hass, "test", request)
    assert response.status == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_webhook.py -v`
Expected: FAIL

- [ ] **Step 3: Implement webhook.py**

```python
"""Webhook handler for Shelter Finder."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response

from homeassistant.core import HomeAssistant

from .const import DOMAIN, THREAT_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_handle_webhook(
    hass: HomeAssistant,
    webhook_id: str,
    request: Request,
) -> Response:
    """Handle incoming webhook for external alert triggers."""
    try:
        data: dict[str, Any] = await request.json()
    except Exception:
        return Response(status=400, text="Invalid JSON")

    threat_type = data.get("threat_type")
    if not threat_type:
        return Response(status=400, text="Missing required field: threat_type")

    if threat_type not in THREAT_TYPES:
        return Response(
            status=400,
            text=f"Unknown threat_type: {threat_type}. Valid: {', '.join(THREAT_TYPES)}",
        )

    source = data.get("source", "unknown")
    message = data.get("message", "")

    _LOGGER.warning(
        "Webhook alert received: type=%s, source=%s, message=%s",
        threat_type, source, message,
    )

    # Find the alert coordinator
    alert_coordinator = hass.data.get(DOMAIN, {}).get("alert_coordinator")
    if alert_coordinator is None:
        return Response(status=500, text="Shelter Finder not initialized")

    alert_coordinator.trigger(threat_type, triggered_by=f"webhook:{source}")
    return Response(status=200, text="Alert triggered")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_webhook.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/webhook.py tests/test_webhook.py
git commit -m "feat: add webhook handler for external alert triggers"
```

---

### Task 13: Integration Setup (__init__.py + services.yaml)

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`
- Create: `custom_components/shelter_finder/services.yaml`
- Create: `tests/test_init.py`

- [ ] **Step 1: Create services.yaml**

```yaml
trigger_alert:
  name: Trigger alert
  description: Trigger a shelter alert for all tracked persons.
  fields:
    threat_type:
      name: Threat type
      description: Type of threat (storm, earthquake, attack, armed_conflict, flood, nuclear_chemical)
      required: true
      selector:
        select:
          options:
            - storm
            - earthquake
            - attack
            - armed_conflict
            - flood
            - nuclear_chemical
    message:
      name: Message
      description: Optional message to include in notifications.
      required: false
      selector:
        text:

cancel_alert:
  name: Cancel alert
  description: Cancel the current shelter alert.

refresh_shelters:
  name: Refresh shelters
  description: Force refresh of the shelter cache from Overpass API.

add_custom_poi:
  name: Add custom POI
  description: Add a custom shelter point of interest.
  fields:
    name:
      name: Name
      description: Name of the shelter.
      required: true
      selector:
        text:
    latitude:
      name: Latitude
      description: GPS latitude.
      required: true
      selector:
        number:
          min: -90
          max: 90
          step: 0.000001
          mode: box
    longitude:
      name: Longitude
      description: GPS longitude.
      required: true
      selector:
        number:
          min: -180
          max: 180
          step: 0.000001
          mode: box
    shelter_type:
      name: Shelter type
      description: Type of shelter.
      required: true
      selector:
        select:
          options:
            - bunker
            - subway
            - civic
            - school
            - worship
            - shelter
            - sports
            - hospital
            - government
    notes:
      name: Notes
      description: Optional notes (access code, hours, etc.)
      required: false
      selector:
        text:

confirm_safe:
  name: Confirm safe
  description: Confirm that a person has reached safety.
  fields:
    person:
      name: Person
      description: Entity ID of the person (e.g., person.alice).
      required: true
      selector:
        entity:
          domain: person
```

- [ ] **Step 2: Write failing tests for init**

```python
"""Tests for Shelter Finder integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.shelter_finder.const import DOMAIN


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, mock_config_entry_data: dict) -> MagicMock:
    """Create a mock config entry."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Shelter Finder",
        data=mock_config_entry_data,
        source="user",
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_setup_entry(hass: HomeAssistant, mock_config_entry: MagicMock) -> None:
    """Test successful setup of config entry."""
    hass.states.async_set("zone.home", "zoning", {"latitude": 48.85, "longitude": 2.35})

    with (
        patch("custom_components.shelter_finder.overpass.OverpassClient.fetch_shelters", new_callable=AsyncMock, return_value=[]),
        patch("custom_components.shelter_finder.coordinator.ShelterUpdateCoordinator._async_update_data", new_callable=AsyncMock, return_value=[]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_unload_entry(hass: HomeAssistant, mock_config_entry: MagicMock) -> None:
    """Test unloading a config entry."""
    hass.states.async_set("zone.home", "zoning", {"latitude": 48.85, "longitude": 2.35})

    with (
        patch("custom_components.shelter_finder.overpass.OverpassClient.fetch_shelters", new_callable=AsyncMock, return_value=[]),
        patch("custom_components.shelter_finder.coordinator.ShelterUpdateCoordinator._async_update_data", new_callable=AsyncMock, return_value=[]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert result is True
    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_init.py -v`
Expected: FAIL

- [ ] **Step 4: Implement full __init__.py**

```python
"""Shelter Finder integration."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
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
    DEFAULT_OVERPASS_URL,
    DEFAULT_RADIUS,
    DEFAULT_RE_NOTIFICATION_INTERVAL,
    DEFAULT_MAX_RE_NOTIFICATIONS,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelter Finder from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Resolve config (options override data)
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

    # Custom OSM tags
    custom_tags_str = config.get(CONF_CUSTOM_OSM_TAGS, "")
    custom_tags = [t.strip() for t in custom_tags_str.split(",") if t.strip()] if custom_tags_str else None

    # Create dependencies
    session = async_get_clientsession(hass)
    storage_dir = Path(hass.config.path(".storage"))
    cache = ShelterCache(storage_dir, ttl_hours=cache_ttl)
    overpass_client = OverpassClient(session=session, url=overpass_url, tags=custom_tags)

    # Create coordinators
    coordinator = ShelterUpdateCoordinator(
        hass=hass,
        cache=cache,
        overpass_client=overpass_client,
        persons=persons,
        search_radius=search_radius,
        adaptive_radius=adaptive_radius,
        adaptive_radius_max=adaptive_radius_max,
    )
    await coordinator.async_config_entry_first_refresh()

    alert_coordinator = AlertCoordinator(
        hass=hass,
        shelter_coordinator=coordinator,
        persons=persons,
        travel_mode=travel_mode,
        re_notification_interval=re_notif_interval,
        max_re_notifications=max_re_notif,
    )

    # Store in hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "alert_coordinator": alert_coordinator,
        "cache": cache,
    }
    # Store alert_coordinator at domain level for webhook access
    hass.data[DOMAIN]["alert_coordinator"] = alert_coordinator

    # Register services (idempotent)
    if not hass.services.has_service(DOMAIN, "trigger_alert"):
        _register_services(hass)

    # Register webhook
    webhook_id = config.get(CONF_WEBHOOK_ID, entry.entry_id)
    webhook.async_register(
        hass, DOMAIN, "Shelter Finder Alert", webhook_id, async_handle_webhook
    )

    # Forward platform setup
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
    webhook.async_unregister(hass, webhook_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Clean up domain-level refs if no entries remain
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
            # Send notifications to each person
            await _send_alert_notifications(hass, ac, message)

    async def handle_cancel_alert(call: ServiceCall) -> None:
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.cancel()

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
                pois = cache.load_pois()
                pois.append({
                    "id": uuid.uuid4().hex,
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "shelter_type": shelter_type,
                    "notes": notes,
                    "source": "manual",
                })
                cache.save_pois(pois)
                # Refresh coordinator to pick up new POI
                if "coordinator" in entry_data:
                    await entry_data["coordinator"].async_request_refresh()

    async def handle_confirm_safe(call: ServiceCall) -> None:
        person = call.data["person"]
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.confirm_safe(person)

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
        schema=vol.Schema({
            vol.Required("person"): cv.string,
        }),
    )


async def _send_alert_notifications(
    hass: HomeAssistant,
    alert_coordinator: AlertCoordinator,
    message: str = "",
) -> None:
    """Send push notifications to all tracked persons."""
    for person_id in alert_coordinator.persons:
        best = alert_coordinator.get_best_shelter(person_id)
        if best is None:
            continue

        person_name = person_id.split(".")[-1]
        device_service = f"mobile_app_{person_name}"

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

        try:
            await hass.services.async_call(
                "notify",
                device_service,
                {
                    "message": notif_message,
                    "title": f"Shelter Finder - {alert_coordinator.threat_type}",
                    "data": {
                        "actions": [
                            {"action": "CONFIRM_SAFE", "title": "Je suis à l'abri"},
                        ],
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

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_init.py -v`
Expected: All 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/shelter_finder/__init__.py custom_components/shelter_finder/services.yaml tests/test_init.py
git commit -m "feat: full integration setup with services, webhook, notifications, and onboarding"
```

---

### Task 14: CI/CD GitHub Actions

**Files:**
- Create: `.github/workflows/tests.yml`
- Create: `.github/workflows/hacs.yml`

- [ ] **Step 1: Create tests.yml**

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements_test.txt

      - name: Run tests with coverage
        run: |
          pytest --cov=custom_components/shelter_finder --cov-report=xml -v

      - name: Upload coverage
        if: matrix.python-version == '3.12'
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          fail_ci_if_error: false
```

- [ ] **Step 2: Create hacs.yml**

```yaml
name: HACS Validation

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: HACS validation
        uses: hacs/action@main
        with:
          category: integration
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/tests.yml .github/workflows/hacs.yml
git commit -m "ci: add GitHub Actions for tests and HACS validation"
```

---

### Task 15: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with installation, configuration, and usage guide"
```

---

## Review Checkpoint

After completing all 15 tasks, run the full test suite:

```bash
pytest --cov=custom_components/shelter_finder --cov-report=term-missing -v
```

Expected: All tests pass, coverage > 70%.

Then push to GitHub:

```bash
git push origin main
```
