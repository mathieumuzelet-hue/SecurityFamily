# Shelter Finder v0.6 — FR-Alert / SAIP Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-trigger Shelter Finder alerts when French government alert systems (Georisques + Meteo France vigilance) detect a threat within a configurable radius of `zone.home`.

**Architecture:** A provider-based polling system. An abstract `AlertProvider` base class exposes `async_fetch_alerts(lat, lon, radius_km) -> list[GouvAlert]`. Two concrete providers — `GeorisquesProvider` and `MeteoFranceProvider` — each hit one public JSON API and map source events to Shelter Finder `THREAT_TYPES`. An `AlertProviderManager` polls active providers on a configurable interval, filters by geographic proximity and minimum severity, deduplicates by `alert_id`, triggers `AlertCoordinator.trigger()` when a new qualifying alert appears, and optionally auto-cancels when the source alert expires.

**Tech Stack:** Python 3.11+, `aiohttp` via `homeassistant.helpers.aiohttp_client.async_get_clientsession`, `asyncio` tasks, `homeassistant.helpers.event.async_track_time_interval`, `dataclasses`, `pytest` + `pytest-asyncio`, `aioresponses` for HTTP mocking.

---

## File Structure

**Create:**
- `custom_components/shelter_finder/alert_providers/__init__.py` — package init, re-exports `AlertProvider`, `GouvAlert`
- `custom_components/shelter_finder/alert_providers/base.py` — `AlertProvider` ABC + `GouvAlert` dataclass + severity helpers
- `custom_components/shelter_finder/alert_providers/georisques.py` — `GeorisquesProvider`
- `custom_components/shelter_finder/alert_providers/meteo_france.py` — `MeteoFranceProvider`
- `custom_components/shelter_finder/alert_provider_manager.py` — orchestrator (`AlertProviderManager`)
- `tests/test_alert_providers_base.py` — tests for `GouvAlert`, severity comparisons
- `tests/test_alert_providers_georisques.py` — Georisques HTTP mock tests
- `tests/test_alert_providers_meteo_france.py` — Meteo France HTTP mock tests
- `tests/test_alert_provider_manager.py` — manager polling, dedup, auto-cancel tests

**Modify:**
- `custom_components/shelter_finder/const.py` — add `CONF_PROVIDER_GEORISQUES`, `CONF_PROVIDER_METEO_FRANCE`, `CONF_POLLING_INTERVAL`, `CONF_ALERT_RADIUS`, `CONF_AUTO_CANCEL`, `CONF_MIN_SEVERITY` with defaults; `SEVERITY_LEVELS` ordering
- `custom_components/shelter_finder/__init__.py` — start `AlertProviderManager` at end of `async_setup_entry`, stop in `async_unload_entry`; route manager-triggered alerts through `_send_alert_notifications`

---

## Task 1: Add provider config constants

**Files:**
- Modify: `custom_components/shelter_finder/const.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_const_provider_keys.py`:

```python
"""Constants regression test for FR-Alert provider config keys."""
from custom_components.shelter_finder import const


def test_provider_conf_keys_present():
    assert const.CONF_PROVIDER_GEORISQUES == "provider_georisques"
    assert const.CONF_PROVIDER_METEO_FRANCE == "provider_meteo_france"
    assert const.CONF_POLLING_INTERVAL == "polling_interval"
    assert const.CONF_ALERT_RADIUS == "alert_radius"
    assert const.CONF_AUTO_CANCEL == "auto_cancel"
    assert const.CONF_MIN_SEVERITY == "min_severity"


def test_provider_defaults():
    assert const.DEFAULT_POLLING_INTERVAL == 60
    assert const.MIN_POLLING_INTERVAL == 30
    assert const.MAX_POLLING_INTERVAL == 300
    assert const.DEFAULT_AUTO_CANCEL is True
    assert const.DEFAULT_MIN_SEVERITY == "severe"


def test_severity_levels_ordered():
    assert const.SEVERITY_LEVELS == ["minor", "moderate", "severe", "extreme"]
    assert const.SEVERITY_RANK["severe"] > const.SEVERITY_RANK["moderate"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_const_provider_keys.py -v`
Expected: FAIL with `AttributeError: module 'custom_components.shelter_finder.const' has no attribute 'CONF_PROVIDER_GEORISQUES'`.

- [ ] **Step 3: Add the constants**

Append to `custom_components/shelter_finder/const.py`:

```python
# ---------------------------------------------------------------------------
# FR-Alert / SAIP provider config (v0.6)
# ---------------------------------------------------------------------------
CONF_PROVIDER_GEORISQUES = "provider_georisques"
CONF_PROVIDER_METEO_FRANCE = "provider_meteo_france"
CONF_POLLING_INTERVAL = "polling_interval"
CONF_ALERT_RADIUS = "alert_radius"
CONF_AUTO_CANCEL = "auto_cancel"
CONF_MIN_SEVERITY = "min_severity"

DEFAULT_POLLING_INTERVAL = 60
MIN_POLLING_INTERVAL = 30
MAX_POLLING_INTERVAL = 300
DEFAULT_AUTO_CANCEL = True
DEFAULT_MIN_SEVERITY = "severe"

SEVERITY_LEVELS = ["minor", "moderate", "severe", "extreme"]
SEVERITY_RANK: dict[str, int] = {level: idx for idx, level in enumerate(SEVERITY_LEVELS)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_const_provider_keys.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/const.py tests/test_const_provider_keys.py
git commit -m "feat(const): add FR-Alert provider config keys and severity levels"
```

---

## Task 2: `GouvAlert` dataclass + `AlertProvider` ABC

**Files:**
- Create: `custom_components/shelter_finder/alert_providers/__init__.py`
- Create: `custom_components/shelter_finder/alert_providers/base.py`
- Create: `tests/test_alert_providers_base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_alert_providers_base.py`:

```python
"""Tests for AlertProvider base class and GouvAlert dataclass."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from custom_components.shelter_finder.alert_providers.base import (
    AlertProvider,
    GouvAlert,
    meets_min_severity,
)


def test_gouv_alert_construction():
    alert = GouvAlert(
        alert_id="gr-42",
        threat_type="flood",
        severity="severe",
        title="Crue de la Seine",
        message="Inondation imminente",
        source="georisques",
        zone_lat=48.85,
        zone_lon=2.35,
        starts_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        expires_at=None,
    )
    assert alert.alert_id == "gr-42"
    assert alert.threat_type == "flood"
    assert alert.source == "georisques"


def test_meets_min_severity_true():
    assert meets_min_severity("severe", "moderate") is True
    assert meets_min_severity("extreme", "severe") is True
    assert meets_min_severity("severe", "severe") is True


def test_meets_min_severity_false():
    assert meets_min_severity("minor", "severe") is False
    assert meets_min_severity("moderate", "severe") is False


def test_meets_min_severity_unknown_treated_as_minor():
    # Unknown input severity must not slip through a severe threshold
    assert meets_min_severity("weird", "severe") is False


def test_alert_provider_is_abstract():
    with pytest.raises(TypeError):
        AlertProvider()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_subclass_works():
    class _Stub(AlertProvider):
        source_name = "stub"

        async def async_fetch_alerts(self, lat, lon, radius_km):
            return []

    stub = _Stub()
    result = await stub.async_fetch_alerts(48.85, 2.35, 5.0)
    assert result == []
    assert stub.source_name == "stub"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_providers_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'custom_components.shelter_finder.alert_providers'`.

- [ ] **Step 3: Create the package and base module**

Create `custom_components/shelter_finder/alert_providers/__init__.py`:

```python
"""Alert provider package for FR-Alert / SAIP sources."""

from .base import AlertProvider, GouvAlert, meets_min_severity

__all__ = ["AlertProvider", "GouvAlert", "meets_min_severity"]
```

Create `custom_components/shelter_finder/alert_providers/base.py`:

```python
"""Base classes for FR-Alert / SAIP providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..const import SEVERITY_RANK


@dataclass
class GouvAlert:
    """A normalized government alert from a French source."""

    alert_id: str
    threat_type: str
    severity: str
    title: str
    message: str
    source: str
    zone_lat: float
    zone_lon: float
    starts_at: datetime
    expires_at: datetime | None


def meets_min_severity(severity: str, minimum: str) -> bool:
    """Return True if `severity` is >= `minimum` on the SEVERITY_LEVELS scale.

    Unknown severity strings are treated as the lowest rank (-1) so they cannot
    accidentally satisfy a threshold.
    """
    actual = SEVERITY_RANK.get(severity, -1)
    threshold = SEVERITY_RANK.get(minimum, -1)
    return actual >= threshold


class AlertProvider(ABC):
    """Abstract provider that fetches normalized GouvAlert objects."""

    source_name: str = "unknown"

    @abstractmethod
    async def async_fetch_alerts(
        self, lat: float, lon: float, radius_km: float
    ) -> list[GouvAlert]:
        """Fetch current alerts near (lat, lon) within radius_km."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alert_providers_base.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/alert_providers/__init__.py custom_components/shelter_finder/alert_providers/base.py tests/test_alert_providers_base.py
git commit -m "feat(providers): add AlertProvider ABC and GouvAlert dataclass"
```

---

## Task 3: `GeorisquesProvider` — fetch + map events

**Files:**
- Create: `custom_components/shelter_finder/alert_providers/georisques.py`
- Create: `tests/test_alert_providers_georisques.py`

Source: `https://georisques.gouv.fr/api/v1/gaspar/risques` (public, no auth). We bbox-filter by radius using `latlon` + `rayon` query params and map `risque` codes to Shelter Finder threat types per spec:
- `risque == "Inondation"` or code starting with `INONDATION` → `flood`
- `risque == "Séisme"` or code starting with `SEISME` → `earthquake`
- `risque == "Industriel"` / `ICPE` / `SEVESO` → `nuclear_chemical`

- [ ] **Step 1: Write the failing test**

Create `tests/test_alert_providers_georisques.py`:

```python
"""Tests for GeorisquesProvider."""
from __future__ import annotations

from datetime import datetime, timezone

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.shelter_finder.alert_providers.georisques import (
    GEORISQUES_BASE_URL,
    GeorisquesProvider,
    _map_risque_to_threat,
)


def test_map_risque_to_threat_flood():
    assert _map_risque_to_threat("Inondation") == "flood"
    assert _map_risque_to_threat("INONDATION_CRUE") == "flood"


def test_map_risque_to_threat_earthquake():
    assert _map_risque_to_threat("Séisme") == "earthquake"
    assert _map_risque_to_threat("SEISME") == "earthquake"


def test_map_risque_to_threat_industrial():
    assert _map_risque_to_threat("Industriel") == "nuclear_chemical"
    assert _map_risque_to_threat("ICPE") == "nuclear_chemical"
    assert _map_risque_to_threat("SEVESO_HAUT") == "nuclear_chemical"


def test_map_risque_to_threat_unknown_returns_none():
    assert _map_risque_to_threat("Unknown") is None


@pytest.mark.asyncio
async def test_fetch_alerts_parses_response():
    payload = {
        "data": [
            {
                "id_gaspar": "GR-FLOOD-1",
                "risque": "Inondation",
                "niveau": "severe",
                "libelle": "Crue de la Seine",
                "description": "Inondation en cours",
                "latitude": 48.856,
                "longitude": 2.351,
                "date_debut": "2026-04-14T10:00:00Z",
                "date_fin": "2026-04-15T10:00:00Z",
            },
            {
                "id_gaspar": "GR-UNKNOWN-1",
                "risque": "Unknown",
                "niveau": "minor",
                "libelle": "Ignored",
                "description": "",
                "latitude": 48.86,
                "longitude": 2.35,
                "date_debut": "2026-04-14T10:00:00Z",
                "date_fin": None,
            },
        ]
    }

    with aioresponses() as mocked:
        mocked.get(
            f"{GEORISQUES_BASE_URL}/gaspar/risques?latlon=2.35%2C48.85&rayon=10",
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            provider = GeorisquesProvider(session=session)
            alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)

    assert len(alerts) == 1
    a = alerts[0]
    assert a.alert_id == "georisques:GR-FLOOD-1"
    assert a.threat_type == "flood"
    assert a.severity == "severe"
    assert a.source == "georisques"
    assert a.zone_lat == 48.856
    assert a.zone_lon == 2.351
    assert a.starts_at == datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc)
    assert a.expires_at == datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_fetch_alerts_http_error_returns_empty():
    with aioresponses() as mocked:
        mocked.get(
            f"{GEORISQUES_BASE_URL}/gaspar/risques?latlon=2.35%2C48.85&rayon=10",
            status=500,
        )
        async with aiohttp.ClientSession() as session:
            provider = GeorisquesProvider(session=session)
            alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)

    assert alerts == []


@pytest.mark.asyncio
async def test_fetch_alerts_timeout_returns_empty():
    with aioresponses() as mocked:
        mocked.get(
            f"{GEORISQUES_BASE_URL}/gaspar/risques?latlon=2.35%2C48.85&rayon=10",
            exception=TimeoutError("boom"),
        )
        async with aiohttp.ClientSession() as session:
            provider = GeorisquesProvider(session=session)
            alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)

    assert alerts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_providers_georisques.py -v`
Expected: FAIL with `ModuleNotFoundError: ... georisques`.

- [ ] **Step 3: Implement the provider**

Create `custom_components/shelter_finder/alert_providers/georisques.py`:

```python
"""Georisques (gouv.fr) alert provider."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .base import AlertProvider, GouvAlert

_LOGGER = logging.getLogger(__name__)

GEORISQUES_BASE_URL = "https://georisques.gouv.fr/api/v1"
HTTP_TIMEOUT_SECONDS = 10


def _map_risque_to_threat(risque: str) -> str | None:
    """Map a Georisques `risque` label/code to a Shelter Finder threat_type."""
    if not risque:
        return None
    upper = risque.upper()
    if "INONDATION" in upper:
        return "flood"
    if "SEISME" in upper or "SÉISME" in risque.upper():
        return "earthquake"
    if upper in {"INDUSTRIEL"} or "ICPE" in upper or "SEVESO" in upper:
        return "nuclear_chemical"
    return None


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    # Normalize trailing Z to +00:00 for fromisoformat
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class GeorisquesProvider(AlertProvider):
    """Fetches active risks from the public Georisques GASPAR API."""

    source_name = "georisques"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_fetch_alerts(
        self, lat: float, lon: float, radius_km: float
    ) -> list[GouvAlert]:
        url = f"{GEORISQUES_BASE_URL}/gaspar/risques"
        # Georisques expects lon,lat order for latlon
        params = {"latlon": f"{lon},{lat}", "rayon": int(max(1, round(radius_km)))}
        try:
            async with self._session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Georisques HTTP %s for %s", resp.status, url)
                    return []
                payload: dict[str, Any] = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.debug("Georisques fetch failed: %s", err)
            return []

        alerts: list[GouvAlert] = []
        for item in payload.get("data", []) or []:
            risque = item.get("risque") or ""
            threat = _map_risque_to_threat(risque)
            if threat is None:
                continue
            raw_id = item.get("id_gaspar") or item.get("id")
            if not raw_id:
                continue
            starts = _parse_iso8601(item.get("date_debut")) or datetime.now(timezone.utc)
            expires = _parse_iso8601(item.get("date_fin"))
            try:
                zone_lat = float(item.get("latitude"))
                zone_lon = float(item.get("longitude"))
            except (TypeError, ValueError):
                continue
            severity = (item.get("niveau") or "moderate").lower()
            alerts.append(
                GouvAlert(
                    alert_id=f"georisques:{raw_id}",
                    threat_type=threat,
                    severity=severity,
                    title=item.get("libelle") or risque,
                    message=item.get("description") or "",
                    source="georisques",
                    zone_lat=zone_lat,
                    zone_lon=zone_lon,
                    starts_at=starts,
                    expires_at=expires,
                )
            )
        return alerts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alert_providers_georisques.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/alert_providers/georisques.py tests/test_alert_providers_georisques.py
git commit -m "feat(providers): add GeorisquesProvider with flood/earthquake/industrial mapping"
```

---

## Task 4: `MeteoFranceProvider` — vigilance JSON

**Files:**
- Create: `custom_components/shelter_finder/alert_providers/meteo_france.py`
- Create: `tests/test_alert_providers_meteo_france.py`

Source: `https://vigilance.meteofrance.fr/data/vigilance.json` (public, no auth). Per spec threat mapping:
- phenomenon "vent" (wind) at color orange/rouge → `storm`
- phenomenon "orages" (thunderstorms) at color orange/rouge → `storm`
- phenomenon "pluie-inondation" at color orange/rouge → `flood`

The public vigilance feed reports per-department. We map a lat/lon to a department code using a simple radius check against a bundled department-centroid table. Any department whose centroid lies within `radius_km + 80km` (a department is ~50km wide) is considered "near" and its alerts are included. Color → severity: `jaune=minor`, `orange=severe`, `rouge=extreme` (green ignored).

- [ ] **Step 1: Write the failing test**

Create `tests/test_alert_providers_meteo_france.py`:

```python
"""Tests for MeteoFranceProvider."""
from __future__ import annotations

from datetime import datetime, timezone

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.shelter_finder.alert_providers.meteo_france import (
    METEO_FRANCE_URL,
    MeteoFranceProvider,
    _color_to_severity,
    _map_phenomenon_to_threat,
    _nearby_department_codes,
)


def test_color_to_severity():
    assert _color_to_severity("rouge") == "extreme"
    assert _color_to_severity("orange") == "severe"
    assert _color_to_severity("jaune") == "minor"
    assert _color_to_severity("vert") is None
    assert _color_to_severity("unknown") is None


def test_map_phenomenon_to_threat():
    assert _map_phenomenon_to_threat("vent") == "storm"
    assert _map_phenomenon_to_threat("Vent violent") == "storm"
    assert _map_phenomenon_to_threat("orages") == "storm"
    assert _map_phenomenon_to_threat("pluie-inondation") == "flood"
    assert _map_phenomenon_to_threat("neige") is None  # not in v0.6 scope


def test_nearby_departments_paris():
    # Paris is 75, close to 92/93/94/77/78/91/95
    codes = _nearby_department_codes(48.85, 2.35, radius_km=20)
    assert "75" in codes


@pytest.mark.asyncio
async def test_fetch_alerts_parses_vigilance():
    payload = {
        "product": {
            "periods": [
                {
                    "text_bloc_items": [],
                    "timelaps": {
                        "domain_ids": [
                            {
                                "domain_id": "75",
                                "phenomenon_items": [
                                    {
                                        "phenomenon_id": "6",
                                        "phenomenon_name": "pluie-inondation",
                                        "phenomenon_max_color_id": 3,
                                        "phenomenon_max_color_name": "orange",
                                    },
                                    {
                                        "phenomenon_id": "2",
                                        "phenomenon_name": "vent",
                                        "phenomenon_max_color_id": 4,
                                        "phenomenon_max_color_name": "rouge",
                                    },
                                ],
                            },
                            {
                                "domain_id": "13",  # far (Marseille) — filtered
                                "phenomenon_items": [
                                    {
                                        "phenomenon_id": "2",
                                        "phenomenon_name": "vent",
                                        "phenomenon_max_color_name": "rouge",
                                    }
                                ],
                            },
                        ]
                    },
                    "begin_validity_time": "2026-04-14T06:00:00Z",
                    "end_validity_time": "2026-04-14T22:00:00Z",
                }
            ]
        }
    }

    with aioresponses() as mocked:
        mocked.get(METEO_FRANCE_URL, payload=payload)
        async with aiohttp.ClientSession() as session:
            provider = MeteoFranceProvider(session=session)
            alerts = await provider.async_fetch_alerts(48.85, 2.35, 20.0)

    assert len(alerts) == 2
    alerts_by_threat = {a.threat_type: a for a in alerts}
    assert "flood" in alerts_by_threat
    assert "storm" in alerts_by_threat
    flood = alerts_by_threat["flood"]
    assert flood.source == "meteo_france"
    assert flood.severity == "severe"
    assert flood.alert_id == "meteo_france:75:pluie-inondation:2026-04-14T06:00:00+00:00"
    assert flood.starts_at == datetime(2026, 4, 14, 6, 0, tzinfo=timezone.utc)
    assert flood.expires_at == datetime(2026, 4, 14, 22, 0, tzinfo=timezone.utc)
    storm = alerts_by_threat["storm"]
    assert storm.severity == "extreme"


@pytest.mark.asyncio
async def test_fetch_alerts_http_error_returns_empty():
    with aioresponses() as mocked:
        mocked.get(METEO_FRANCE_URL, status=503)
        async with aiohttp.ClientSession() as session:
            provider = MeteoFranceProvider(session=session)
            alerts = await provider.async_fetch_alerts(48.85, 2.35, 20.0)
    assert alerts == []


@pytest.mark.asyncio
async def test_fetch_alerts_green_department_yields_no_alerts():
    payload = {
        "product": {
            "periods": [
                {
                    "timelaps": {
                        "domain_ids": [
                            {
                                "domain_id": "75",
                                "phenomenon_items": [
                                    {
                                        "phenomenon_name": "vent",
                                        "phenomenon_max_color_name": "vert",
                                    }
                                ],
                            }
                        ]
                    },
                    "begin_validity_time": "2026-04-14T06:00:00Z",
                    "end_validity_time": "2026-04-14T22:00:00Z",
                }
            ]
        }
    }
    with aioresponses() as mocked:
        mocked.get(METEO_FRANCE_URL, payload=payload)
        async with aiohttp.ClientSession() as session:
            provider = MeteoFranceProvider(session=session)
            alerts = await provider.async_fetch_alerts(48.85, 2.35, 20.0)
    assert alerts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_providers_meteo_france.py -v`
Expected: FAIL with `ModuleNotFoundError: ... meteo_france`.

- [ ] **Step 3: Implement the provider**

Create `custom_components/shelter_finder/alert_providers/meteo_france.py`:

```python
"""Meteo France vigilance alert provider (public JSON feed)."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .base import AlertProvider, GouvAlert

_LOGGER = logging.getLogger(__name__)

METEO_FRANCE_URL = "https://vigilance.meteofrance.fr/data/vigilance.json"
HTTP_TIMEOUT_SECONDS = 10

# Department centroid table (code -> (lat, lon)). Metropolitan France + Corsica.
# Centroids are approximate; precision to 0.1 deg is sufficient because we
# buffer with `radius_km + 80km` to cover a whole department.
DEPARTMENT_CENTROIDS: dict[str, tuple[float, float]] = {
    "01": (46.20, 5.35), "02": (49.55, 3.55), "03": (46.40, 3.20),
    "04": (44.10, 6.25), "05": (44.65, 6.30), "06": (43.95, 7.15),
    "07": (44.75, 4.40), "08": (49.60, 4.65), "09": (42.95, 1.50),
    "10": (48.30, 4.15), "11": (43.10, 2.45), "12": (44.30, 2.75),
    "13": (43.55, 5.10), "14": (49.10, -0.35), "15": (45.05, 2.65),
    "16": (45.70, 0.15), "17": (45.75, -0.65), "18": (47.05, 2.50),
    "19": (45.35, 1.85), "21": (47.40, 4.80), "22": (48.40, -2.85),
    "23": (46.10, 2.05), "24": (45.10, 0.75), "25": (47.15, 6.40),
    "26": (44.70, 5.15), "27": (49.10, 0.95), "28": (48.45, 1.45),
    "29": (48.25, -4.05), "2A": (41.85, 8.90), "2B": (42.40, 9.20),
    "30": (44.05, 4.25), "31": (43.40, 1.45), "32": (43.65, 0.50),
    "33": (44.85, -0.55), "34": (43.60, 3.45), "35": (48.15, -1.65),
    "36": (46.80, 1.55), "37": (47.30, 0.75), "38": (45.25, 5.65),
    "39": (46.75, 5.65), "40": (43.95, -0.75), "41": (47.60, 1.45),
    "42": (45.65, 4.30), "43": (45.10, 3.85), "44": (47.30, -1.65),
    "45": (47.90, 2.25), "46": (44.60, 1.65), "47": (44.35, 0.65),
    "48": (44.50, 3.55), "49": (47.35, -0.55), "50": (49.10, -1.10),
    "51": (49.00, 4.35), "52": (48.10, 5.15), "53": (48.10, -0.65),
    "54": (48.70, 6.15), "55": (48.95, 5.40), "56": (47.85, -2.80),
    "57": (49.05, 6.60), "58": (47.05, 3.50), "59": (50.45, 3.15),
    "60": (49.40, 2.45), "61": (48.60, 0.15), "62": (50.45, 2.45),
    "63": (45.75, 3.15), "64": (43.25, -0.75), "65": (43.05, 0.15),
    "66": (42.60, 2.55), "67": (48.65, 7.65), "68": (47.95, 7.35),
    "69": (45.75, 4.70), "70": (47.65, 6.15), "71": (46.60, 4.50),
    "72": (48.00, 0.20), "73": (45.45, 6.65), "74": (46.00, 6.45),
    "75": (48.85, 2.35), "76": (49.65, 1.05), "77": (48.55, 3.05),
    "78": (48.80, 1.95), "79": (46.55, -0.25), "80": (49.95, 2.30),
    "81": (43.85, 2.15), "82": (44.05, 1.40), "83": (43.45, 6.25),
    "84": (44.00, 5.15), "85": (46.70, -1.40), "86": (46.55, 0.45),
    "87": (45.90, 1.25), "88": (48.20, 6.45), "89": (47.80, 3.55),
    "90": (47.65, 6.95), "91": (48.50, 2.25), "92": (48.85, 2.25),
    "93": (48.90, 2.50), "94": (48.80, 2.45), "95": (49.05, 2.15),
}

_WIND_KEYWORDS = {"vent"}
_STORM_KEYWORDS = {"orages", "orage"}
_FLOOD_KEYWORDS = {"pluie-inondation", "inondation", "crues"}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _nearby_department_codes(lat: float, lon: float, radius_km: float) -> set[str]:
    """Return department codes whose centroid is within radius_km + 80km buffer."""
    buffer = radius_km + 80.0
    return {
        code
        for code, (dlat, dlon) in DEPARTMENT_CENTROIDS.items()
        if _haversine_km(lat, lon, dlat, dlon) <= buffer
    }


def _color_to_severity(color: str | None) -> str | None:
    if not color:
        return None
    c = color.lower()
    if c == "rouge":
        return "extreme"
    if c == "orange":
        return "severe"
    if c == "jaune":
        return "minor"
    return None


def _map_phenomenon_to_threat(name: str | None) -> str | None:
    if not name:
        return None
    n = name.lower()
    for kw in _FLOOD_KEYWORDS:
        if kw in n:
            return "flood"
    for kw in _STORM_KEYWORDS:
        if kw in n:
            return "storm"
    for kw in _WIND_KEYWORDS:
        if kw in n:
            return "storm"
    return None


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class MeteoFranceProvider(AlertProvider):
    """Public Meteo France vigilance JSON feed."""

    source_name = "meteo_france"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_fetch_alerts(
        self, lat: float, lon: float, radius_km: float
    ) -> list[GouvAlert]:
        try:
            async with self._session.get(
                METEO_FRANCE_URL,
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Meteo France HTTP %s", resp.status)
                    return []
                payload: dict[str, Any] = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.debug("Meteo France fetch failed: %s", err)
            return []

        nearby = _nearby_department_codes(lat, lon, radius_km)
        alerts: list[GouvAlert] = []
        periods = payload.get("product", {}).get("periods", []) or []
        for period in periods:
            starts = _parse_iso8601(period.get("begin_validity_time")) or datetime.now(timezone.utc)
            expires = _parse_iso8601(period.get("end_validity_time"))
            starts_iso = starts.isoformat()
            domain_ids = (period.get("timelaps") or {}).get("domain_ids", []) or []
            for dom in domain_ids:
                dep = str(dom.get("domain_id") or "")
                if dep not in nearby:
                    continue
                dep_lat, dep_lon = DEPARTMENT_CENTROIDS[dep]
                for phen in dom.get("phenomenon_items", []) or []:
                    name = phen.get("phenomenon_name")
                    color = phen.get("phenomenon_max_color_name")
                    threat = _map_phenomenon_to_threat(name)
                    severity = _color_to_severity(color)
                    if threat is None or severity is None:
                        continue
                    alerts.append(
                        GouvAlert(
                            alert_id=f"meteo_france:{dep}:{name}:{starts_iso}",
                            threat_type=threat,
                            severity=severity,
                            title=f"Vigilance {color} {name} ({dep})",
                            message=f"Vigilance Meteo France {color} pour {name} sur le departement {dep}",
                            source="meteo_france",
                            zone_lat=dep_lat,
                            zone_lon=dep_lon,
                            starts_at=starts,
                            expires_at=expires,
                        )
                    )
        return alerts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alert_providers_meteo_france.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/alert_providers/meteo_france.py tests/test_alert_providers_meteo_france.py
git commit -m "feat(providers): add MeteoFranceProvider for vigilance storm/flood alerts"
```

---

## Task 5: `AlertProviderManager` — polling, dedup, trigger, auto-cancel

**Files:**
- Create: `custom_components/shelter_finder/alert_provider_manager.py`
- Create: `tests/test_alert_provider_manager.py`

Responsibilities:
1. Hold a list of active providers and polling config.
2. On each tick (`async_poll_once`) gather alerts from all providers concurrently.
3. Filter: haversine distance from `zone.home` <= `radius_km`; severity >= `min_severity`.
4. Track known alert IDs in a set. A *new* qualifying alert whose ID is not already known AND there is no active Shelter Finder alert triggers `alert_coordinator.trigger(threat_type, triggered_by=f"provider:{source}")`.
5. When a previously-known alert disappears from all provider responses AND `auto_cancel` is True AND the coordinator's triggering source matches, call `alert_coordinator.cancel()`.
6. `async_start()` schedules `async_poll_once` every `polling_interval` seconds via `async_track_time_interval`. `async_stop()` cancels the scheduled callback and any in-flight task.

- [ ] **Step 1: Write the failing test**

Create `tests/test_alert_provider_manager.py`:

```python
"""Tests for AlertProviderManager orchestration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.shelter_finder.alert_provider_manager import (
    AlertProviderManager,
)
from custom_components.shelter_finder.alert_providers.base import (
    AlertProvider,
    GouvAlert,
)


class _FakeProvider(AlertProvider):
    source_name = "fake"

    def __init__(self, alerts: list[GouvAlert]):
        self._alerts = alerts
        self.calls = 0

    async def async_fetch_alerts(self, lat, lon, radius_km):
        self.calls += 1
        return list(self._alerts)


class _FakeCoordinator:
    def __init__(self):
        self._active = False
        self._threat: str | None = None
        self._by: str | None = None
        self.trigger_calls: list[tuple[str, str]] = []
        self.cancel_calls = 0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def triggered_by(self) -> str | None:
        return self._by

    def trigger(self, threat_type: str, triggered_by: str = "manual") -> None:
        self._active = True
        self._threat = threat_type
        self._by = triggered_by
        self.trigger_calls.append((threat_type, triggered_by))

    def cancel(self) -> None:
        self._active = False
        self._threat = None
        self._by = None
        self.cancel_calls += 1


def _alert(alert_id: str, threat: str = "flood", severity: str = "severe",
           lat: float = 48.85, lon: float = 2.35,
           expires: datetime | None = None) -> GouvAlert:
    return GouvAlert(
        alert_id=alert_id,
        threat_type=threat,
        severity=severity,
        title="t",
        message="m",
        source="fake",
        zone_lat=lat,
        zone_lon=lon,
        starts_at=datetime.now(timezone.utc),
        expires_at=expires,
    )


def _make_hass_with_home(lat=48.85, lon=2.35):
    hass = MagicMock()
    zone_state = MagicMock()
    zone_state.attributes = {"latitude": lat, "longitude": lon, "radius": 100}
    hass.states.get = MagicMock(return_value=zone_state)
    return hass


@pytest.mark.asyncio
async def test_poll_triggers_alert_when_matching():
    provider = _FakeProvider([_alert("a1", threat="flood", severity="severe")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert coord.trigger_calls == [("flood", "provider:fake")]
    assert "a1" in mgr.known_alert_ids


@pytest.mark.asyncio
async def test_poll_ignores_below_min_severity():
    provider = _FakeProvider([_alert("a1", severity="moderate")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert coord.trigger_calls == []
    assert mgr.known_alert_ids == set()


@pytest.mark.asyncio
async def test_poll_filters_by_distance():
    # Alert at (46, 2) — ~300km from Paris
    provider = _FakeProvider([_alert("a1", lat=46.0, lon=2.0)])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(48.85, 2.35),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert coord.trigger_calls == []


@pytest.mark.asyncio
async def test_poll_dedupes_existing_alert_id():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()
    await mgr.async_poll_once()

    assert len(coord.trigger_calls) == 1  # not re-triggered


@pytest.mark.asyncio
async def test_auto_cancel_when_alert_disappears():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )
    await mgr.async_poll_once()
    assert coord.trigger_calls

    provider._alerts = []  # source now returns nothing
    await mgr.async_poll_once()

    assert coord.cancel_calls == 1
    assert "a1" not in mgr.known_alert_ids


@pytest.mark.asyncio
async def test_auto_cancel_disabled_keeps_alert_active():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=False,
        min_severity="severe",
    )
    await mgr.async_poll_once()
    provider._alerts = []
    await mgr.async_poll_once()

    assert coord.cancel_calls == 0


@pytest.mark.asyncio
async def test_auto_cancel_only_cancels_own_trigger():
    """If the active alert was triggered manually, manager must not cancel it."""
    provider = _FakeProvider([])
    coord = _FakeCoordinator()
    coord.trigger("storm", triggered_by="manual")
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert coord.cancel_calls == 0


@pytest.mark.asyncio
async def test_does_not_trigger_when_alert_already_active():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    coord.trigger("attack", triggered_by="manual")  # something else is active
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    # coord.trigger_calls = [("attack","manual")] from setup; no new call
    assert coord.trigger_calls == [("attack", "manual")]


@pytest.mark.asyncio
async def test_trigger_callback_called_on_trigger():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    calls: list[int] = []
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: calls.append(1),
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert calls == [1]


@pytest.mark.asyncio
async def test_no_zone_home_skips_poll():
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=hass,
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert provider.calls == 0
    assert coord.trigger_calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_provider_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: ... alert_provider_manager`.

- [ ] **Step 3: Implement the manager**

Create `custom_components/shelter_finder/alert_provider_manager.py`:

```python
"""Orchestrator for FR-Alert / SAIP providers."""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import timedelta
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .alert_coordinator import AlertCoordinator
from .alert_providers.base import AlertProvider, GouvAlert, meets_min_severity

_LOGGER = logging.getLogger(__name__)

_PROVIDER_TRIGGER_PREFIX = "provider:"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class AlertProviderManager:
    """Polls providers, filters alerts, drives AlertCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        providers: list[AlertProvider],
        alert_coordinator: AlertCoordinator,
        trigger_callback: Callable[[], None],
        polling_interval: int,
        radius_km: float,
        auto_cancel: bool,
        min_severity: str,
        zone_entity_id: str = "zone.home",
    ) -> None:
        self._hass = hass
        self._providers = providers
        self._coord = alert_coordinator
        self._trigger_callback = trigger_callback
        self._polling_interval = polling_interval
        self._radius_km = radius_km
        self._auto_cancel = auto_cancel
        self._min_severity = min_severity
        self._zone_entity_id = zone_entity_id
        self._known_alert_ids: set[str] = set()
        self._active_alert_id: str | None = None
        self._unsub: Callable[[], None] | None = None
        self._in_flight: asyncio.Task | None = None

    @property
    def known_alert_ids(self) -> set[str]:
        return set(self._known_alert_ids)

    async def async_start(self) -> None:
        """Start periodic polling."""
        if self._unsub is not None:
            return
        # Fire once immediately so the first poll does not wait a full interval
        await self.async_poll_once()
        self._unsub = async_track_time_interval(
            self._hass,
            self._scheduled_tick,
            timedelta(seconds=self._polling_interval),
        )
        _LOGGER.info(
            "AlertProviderManager started: %d provider(s), interval=%ss, radius=%skm",
            len(self._providers), self._polling_interval, self._radius_km,
        )

    async def async_stop(self) -> None:
        """Stop periodic polling."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._in_flight is not None and not self._in_flight.done():
            self._in_flight.cancel()
            try:
                await self._in_flight
            except (asyncio.CancelledError, Exception):  # pragma: no cover
                pass
        self._in_flight = None

    async def _scheduled_tick(self, _now) -> None:
        if self._in_flight is not None and not self._in_flight.done():
            _LOGGER.debug("Previous poll still running, skipping tick")
            return
        self._in_flight = self._hass.async_create_task(self.async_poll_once())

    async def async_poll_once(self) -> None:
        """Run one full poll cycle across all providers."""
        home = self._hass.states.get(self._zone_entity_id)
        if home is None:
            _LOGGER.debug("%s not available, skipping poll", self._zone_entity_id)
            return
        home_lat = home.attributes.get("latitude")
        home_lon = home.attributes.get("longitude")
        if home_lat is None or home_lon is None:
            _LOGGER.debug("zone.home has no coordinates, skipping poll")
            return

        # Fetch from all providers concurrently; a provider error yields [].
        results = await asyncio.gather(
            *[p.async_fetch_alerts(home_lat, home_lon, self._radius_km) for p in self._providers],
            return_exceptions=True,
        )
        collected: list[GouvAlert] = []
        for provider, res in zip(self._providers, results):
            if isinstance(res, Exception):
                _LOGGER.warning("Provider %s errored: %s", provider.source_name, res)
                continue
            collected.extend(res)

        # Filter by severity and distance.
        qualifying: list[GouvAlert] = []
        for alert in collected:
            if not meets_min_severity(alert.severity, self._min_severity):
                continue
            dist = _haversine_km(home_lat, home_lon, alert.zone_lat, alert.zone_lon)
            if dist > self._radius_km:
                continue
            qualifying.append(alert)

        qualifying_ids = {a.alert_id for a in qualifying}

        # Trigger on the first new qualifying alert if nothing active.
        for alert in qualifying:
            if alert.alert_id in self._known_alert_ids:
                continue
            self._known_alert_ids.add(alert.alert_id)
            if self._coord.is_active:
                _LOGGER.debug("Alert already active, not re-triggering for %s", alert.alert_id)
                continue
            self._coord.trigger(
                alert.threat_type,
                triggered_by=f"{_PROVIDER_TRIGGER_PREFIX}{alert.source}",
            )
            self._active_alert_id = alert.alert_id
            _LOGGER.info(
                "FR-Alert triggered %s (%s, %s) from %s",
                alert.threat_type, alert.severity, alert.alert_id, alert.source,
            )
            try:
                self._trigger_callback()
            except Exception:  # pragma: no cover
                _LOGGER.exception("trigger_callback raised")
            break

        # Drop IDs that are gone from the source so they can re-trigger later.
        self._known_alert_ids &= qualifying_ids | ({self._active_alert_id} if self._active_alert_id else set())

        # Auto-cancel only if we own the active alert and it disappeared.
        if (
            self._auto_cancel
            and self._coord.is_active
            and self._active_alert_id is not None
            and self._active_alert_id not in qualifying_ids
            and (self._coord.triggered_by or "").startswith(_PROVIDER_TRIGGER_PREFIX)
        ):
            _LOGGER.info("FR-Alert auto-cancelling %s (no longer in source)", self._active_alert_id)
            self._coord.cancel()
            self._known_alert_ids.discard(self._active_alert_id)
            self._active_alert_id = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alert_provider_manager.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/alert_provider_manager.py tests/test_alert_provider_manager.py
git commit -m "feat(manager): add AlertProviderManager with polling, dedup, auto-cancel"
```

---

## Task 6: Wire the manager into `async_setup_entry` / `async_unload_entry`

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`
- Create: `tests/test_init_fr_alert_wiring.py`

Behavior:
- Read the 6 provider CONF_* keys with defaults.
- Build provider list based on which checkboxes are enabled (at least one required, else manager is not created).
- Instantiate `AlertProviderManager` with a `trigger_callback` that calls `_notify_coordinators(hass)` and schedules `_send_alert_notifications(hass, alert_coordinator, "")` on the event loop.
- Store manager in `hass.data[DOMAIN][entry.entry_id]["alert_provider_manager"]`.
- Call `await manager.async_start()` at the end of `async_setup_entry`.
- Call `await manager.async_stop()` at the start of `async_unload_entry`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_init_fr_alert_wiring.py`:

```python
"""Integration wiring tests for FR-Alert manager lifecycle."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.shelter_finder import const
from custom_components.shelter_finder import __init__ as sf_init


@pytest.mark.asyncio
async def test_build_alert_provider_manager_both_enabled():
    hass = MagicMock()
    hass.helpers = MagicMock()
    session = MagicMock()

    config = {
        const.CONF_PROVIDER_GEORISQUES: True,
        const.CONF_PROVIDER_METEO_FRANCE: True,
        const.CONF_POLLING_INTERVAL: 90,
        const.CONF_ALERT_RADIUS: 15,
        const.CONF_AUTO_CANCEL: False,
        const.CONF_MIN_SEVERITY: "moderate",
    }
    alert_coord = MagicMock()
    manager = sf_init._build_alert_provider_manager(
        hass=hass,
        session=session,
        config=config,
        alert_coordinator=alert_coord,
        trigger_callback=lambda: None,
    )

    assert manager is not None
    assert len(manager._providers) == 2
    assert manager._polling_interval == 90
    assert manager._radius_km == 15
    assert manager._auto_cancel is False
    assert manager._min_severity == "moderate"


@pytest.mark.asyncio
async def test_build_alert_provider_manager_none_enabled_returns_none():
    hass = MagicMock()
    session = MagicMock()
    config = {
        const.CONF_PROVIDER_GEORISQUES: False,
        const.CONF_PROVIDER_METEO_FRANCE: False,
    }
    manager = sf_init._build_alert_provider_manager(
        hass=hass,
        session=session,
        config=config,
        alert_coordinator=MagicMock(),
        trigger_callback=lambda: None,
    )
    assert manager is None


@pytest.mark.asyncio
async def test_build_alert_provider_manager_clamps_polling_interval():
    hass = MagicMock()
    session = MagicMock()
    config = {
        const.CONF_PROVIDER_GEORISQUES: True,
        const.CONF_PROVIDER_METEO_FRANCE: False,
        const.CONF_POLLING_INTERVAL: 5,   # below min
    }
    manager = sf_init._build_alert_provider_manager(
        hass=hass, session=session, config=config,
        alert_coordinator=MagicMock(), trigger_callback=lambda: None,
    )
    assert manager is not None
    assert manager._polling_interval == const.MIN_POLLING_INTERVAL

    config[const.CONF_POLLING_INTERVAL] = 9999
    manager2 = sf_init._build_alert_provider_manager(
        hass=hass, session=session, config=config,
        alert_coordinator=MagicMock(), trigger_callback=lambda: None,
    )
    assert manager2._polling_interval == const.MAX_POLLING_INTERVAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_init_fr_alert_wiring.py -v`
Expected: FAIL with `AttributeError: module ... has no attribute '_build_alert_provider_manager'`.

- [ ] **Step 3: Add the builder and wire lifecycle**

Edit `custom_components/shelter_finder/__init__.py`.

Add imports near the existing imports block:

```python
from .alert_provider_manager import AlertProviderManager
from .alert_providers.georisques import GeorisquesProvider
from .alert_providers.meteo_france import MeteoFranceProvider
from .const import (
    CONF_ALERT_RADIUS,
    CONF_AUTO_CANCEL,
    CONF_MIN_SEVERITY,
    CONF_POLLING_INTERVAL,
    CONF_PROVIDER_GEORISQUES,
    CONF_PROVIDER_METEO_FRANCE,
    DEFAULT_AUTO_CANCEL,
    DEFAULT_MIN_SEVERITY,
    DEFAULT_POLLING_INTERVAL,
    MAX_POLLING_INTERVAL,
    MIN_POLLING_INTERVAL,
)
```

Add the builder function below `_register_frontend`:

```python
def _build_alert_provider_manager(
    hass: HomeAssistant,
    session,
    config: dict,
    alert_coordinator: AlertCoordinator,
    trigger_callback,
) -> AlertProviderManager | None:
    """Build the FR-Alert manager from config; returns None if no provider is enabled."""
    providers = []
    if config.get(CONF_PROVIDER_GEORISQUES, False):
        providers.append(GeorisquesProvider(session=session))
    if config.get(CONF_PROVIDER_METEO_FRANCE, False):
        providers.append(MeteoFranceProvider(session=session))
    if not providers:
        return None

    raw_interval = int(config.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL))
    polling_interval = max(MIN_POLLING_INTERVAL, min(MAX_POLLING_INTERVAL, raw_interval))

    # Default alert radius = same as shelter search radius (converted to km)
    search_radius_m = config.get(CONF_SEARCH_RADIUS, DEFAULT_RADIUS)
    default_radius_km = float(search_radius_m) / 1000.0
    radius_km = float(config.get(CONF_ALERT_RADIUS, default_radius_km))

    return AlertProviderManager(
        hass=hass,
        providers=providers,
        alert_coordinator=alert_coordinator,
        trigger_callback=trigger_callback,
        polling_interval=polling_interval,
        radius_km=radius_km,
        auto_cancel=bool(config.get(CONF_AUTO_CANCEL, DEFAULT_AUTO_CANCEL)),
        min_severity=config.get(CONF_MIN_SEVERITY, DEFAULT_MIN_SEVERITY),
    )
```

In `async_setup_entry`, immediately after the existing `hass.data[DOMAIN]["alert_coordinator"] = alert_coordinator` line, add:

```python
    def _on_provider_trigger() -> None:
        _notify_coordinators(hass)
        hass.async_create_task(
            _send_alert_notifications(hass, alert_coordinator, "")
        )

    provider_manager = _build_alert_provider_manager(
        hass=hass,
        session=session,
        config=config,
        alert_coordinator=alert_coordinator,
        trigger_callback=_on_provider_trigger,
    )
    hass.data[DOMAIN][entry.entry_id]["alert_provider_manager"] = provider_manager
    if provider_manager is not None:
        await provider_manager.async_start()
```

In `async_unload_entry`, before `unload_ok = await hass.config_entries.async_unload_platforms(...)`, add:

```python
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    provider_manager = entry_data.get("alert_provider_manager")
    if provider_manager is not None:
        await provider_manager.async_stop()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_init_fr_alert_wiring.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full FR-Alert test suite**

Run:
```
pytest tests/test_const_provider_keys.py tests/test_alert_providers_base.py tests/test_alert_providers_georisques.py tests/test_alert_providers_meteo_france.py tests/test_alert_provider_manager.py tests/test_init_fr_alert_wiring.py -v
```
Expected: all green (34 tests total across the six files).

- [ ] **Step 6: Commit**

```bash
git add custom_components/shelter_finder/__init__.py tests/test_init_fr_alert_wiring.py
git commit -m "feat(init): wire AlertProviderManager into setup/unload lifecycle"
```

---

## Task 7: End-to-end smoke test with mocked HTTP

**Files:**
- Create: `tests/test_fr_alert_e2e.py`

Exercises the whole pipeline: real `GeorisquesProvider` + `MeteoFranceProvider` instances, real `AlertProviderManager`, a stub `AlertCoordinator`, with both source HTTP endpoints mocked. Verifies one full cycle end-to-end.

- [ ] **Step 1: Write the failing test**

Create `tests/test_fr_alert_e2e.py`:

```python
"""End-to-end FR-Alert pipeline test with mocked HTTP."""
from __future__ import annotations

from unittest.mock import MagicMock

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.shelter_finder.alert_provider_manager import AlertProviderManager
from custom_components.shelter_finder.alert_providers.georisques import (
    GEORISQUES_BASE_URL,
    GeorisquesProvider,
)
from custom_components.shelter_finder.alert_providers.meteo_france import (
    METEO_FRANCE_URL,
    MeteoFranceProvider,
)


class _StubCoord:
    def __init__(self):
        self._active = False
        self._by = None
        self.trigger_calls = []
        self.cancel_calls = 0

    @property
    def is_active(self): return self._active
    @property
    def triggered_by(self): return self._by

    def trigger(self, threat_type, triggered_by="manual"):
        self._active = True
        self._by = triggered_by
        self.trigger_calls.append((threat_type, triggered_by))

    def cancel(self):
        self._active = False
        self._by = None
        self.cancel_calls += 1


@pytest.mark.asyncio
async def test_end_to_end_georisques_and_meteo_france():
    hass = MagicMock()
    zone = MagicMock()
    zone.attributes = {"latitude": 48.85, "longitude": 2.35}
    hass.states.get = MagicMock(return_value=zone)

    gr_payload = {
        "data": [
            {
                "id_gaspar": "CRUE-1",
                "risque": "Inondation",
                "niveau": "severe",
                "libelle": "Crue Seine",
                "description": "",
                "latitude": 48.86,
                "longitude": 2.34,
                "date_debut": "2026-04-14T08:00:00Z",
                "date_fin": None,
            }
        ]
    }
    mf_payload = {
        "product": {
            "periods": [
                {
                    "timelaps": {
                        "domain_ids": [
                            {
                                "domain_id": "75",
                                "phenomenon_items": [
                                    {
                                        "phenomenon_name": "vent",
                                        "phenomenon_max_color_name": "rouge",
                                    }
                                ],
                            }
                        ]
                    },
                    "begin_validity_time": "2026-04-14T06:00:00Z",
                    "end_validity_time": "2026-04-14T20:00:00Z",
                }
            ]
        }
    }

    async with aiohttp.ClientSession() as session:
        with aioresponses() as mocked:
            mocked.get(
                f"{GEORISQUES_BASE_URL}/gaspar/risques?latlon=2.35%2C48.85&rayon=10",
                payload=gr_payload,
            )
            mocked.get(METEO_FRANCE_URL, payload=mf_payload)

            coord = _StubCoord()
            callback_calls: list[int] = []
            mgr = AlertProviderManager(
                hass=hass,
                providers=[
                    GeorisquesProvider(session=session),
                    MeteoFranceProvider(session=session),
                ],
                alert_coordinator=coord,
                trigger_callback=lambda: callback_calls.append(1),
                polling_interval=60,
                radius_km=10.0,
                auto_cancel=True,
                min_severity="severe",
            )

            await mgr.async_poll_once()

    # First qualifying alert (either source) should trigger exactly one call.
    assert len(coord.trigger_calls) == 1
    threat, by = coord.trigger_calls[0]
    assert threat in {"flood", "storm"}
    assert by.startswith("provider:")
    assert callback_calls == [1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fr_alert_e2e.py -v`
Expected: PASS already (pipeline is built). If it fails, fix and re-run — this is a safety net against regressions from earlier tasks.

- [ ] **Step 3: Commit**

```bash
git add tests/test_fr_alert_e2e.py
git commit -m "test(fr-alert): end-to-end smoke test with mocked Georisques + Meteo France"
```

---

## Self-Review Notes

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `AlertProvider` ABC with `async_fetch_alerts` | Task 2 |
| `GouvAlert` dataclass with spec fields | Task 2 |
| GeorisquesProvider (floods, earthquakes, industrial) | Task 3 |
| MeteoFranceProvider (wind, orages → storm; pluie-inondation → flood) | Task 4 |
| AlertProviderManager polling every 60s default | Task 5 (+ Task 6 wiring) |
| Filter by radius_km around zone.home | Task 5 |
| Trigger `shelter_finder.trigger_alert` on new match | Task 5, Task 6 |
| Dedup by alert_id | Task 5 |
| Auto-cancel when alert disappears (configurable) | Task 5 |
| Min-severity threshold | Task 5 |
| Config keys CONF_PROVIDER_*, CONF_POLLING_INTERVAL, CONF_ALERT_RADIUS, CONF_AUTO_CANCEL, CONF_MIN_SEVERITY | Task 1 (assumed by upstream OptionsFlow plan; defaults + severity constants added here) |
| Start manager in setup, stop in unload | Task 6 |

**Placeholder scan:** No TBD / TODO / "add validation" / bare "similar to" references. Every code step contains concrete implementation or test code.

**Type consistency:** `AlertProvider.source_name`, `GouvAlert.*` fields, `AlertProviderManager.__init__` kwargs, and `_build_alert_provider_manager` kwargs all match between definition (Tasks 2/5/6) and consumer call sites (Tasks 5/6/7). `alert_coordinator.trigger(threat_type, triggered_by=...)` signature matches existing `AlertCoordinator.trigger` in `alert_coordinator.py` (already accepts that kwarg). `async_track_time_interval` callback signature is `(now)` — matches `_scheduled_tick(self, _now)`.

**Note on OptionsFlow:** The spec and user assumption state that `CONF_PROVIDER_*` keys and their collection via the "Sources" step are handled by a separate, already-merged OptionsFlow plan. This plan therefore only adds the defaults + severity constants and the lifecycle wiring — it does not modify `config_flow.py`.
