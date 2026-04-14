# Shelter Finder v0.6 — OSRM Real Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace haversine straight-line distance/ETA with real walking (or driving) route distance and duration computed by OSRM, with transparent fallback to haversine when OSRM is disabled or unreachable.

**Architecture:** Introduce a `RoutingService` class in `routing.py` that wraps OSRM HTTP calls and exposes a single `async_get_route()` coroutine returning a `RouteResult` dataclass (`distance_m`, `eta_seconds`, `source`). The service owns an in-memory LRU+TTL cache and a warning-throttle counter. It is instantiated once in `__init__.py` and injected into `AlertCoordinator` and the sensor entities via `hass.data[DOMAIN][entry.entry_id]["routing_service"]`. When OSRM is disabled (config) or any call fails (timeout/HTTP/connection), the service returns a haversine-derived `RouteResult` with `source="haversine"`. The sensor/alert pathways become async to await the service. A top-N haversine prefilter keeps OSRM calls bounded for large shelter sets.

**Tech Stack:** Python 3.12 asyncio, `aiohttp` (via `homeassistant.helpers.aiohttp_client.async_get_clientsession`), dataclasses, `collections.OrderedDict` (LRU), pytest + pytest-asyncio, `aioresponses` for HTTP mocking (already used in `tests/test_overpass.py`).

**Assumed pre-existing from the OptionsFlow plan:**
- `const.py` already defines `CONF_OSRM_ENABLED`, `CONF_OSRM_URL`, `CONF_OSRM_MODE`, `CONF_TRANSPORT_MODE` (values: `"foot"`, `"driving"`) and defaults `DEFAULT_OSRM_URL = "https://router.project-osrm.org"`, `DEFAULT_OSRM_MODE = "public"`, `DEFAULT_TRANSPORT_MODE = "foot"`.
- The options step "Routage" collects these keys into `entry.options`.

---

## File Structure

- **Modify** `custom_components/shelter_finder/routing.py` — add `RouteResult`, `RoutingService`, keep existing `haversine_distance` / `calculate_eta_minutes`.
- **Modify** `custom_components/shelter_finder/__init__.py` — instantiate `RoutingService` in `async_setup_entry`, store it in `hass.data`, pass to `AlertCoordinator`.
- **Modify** `custom_components/shelter_finder/alert_coordinator.py` — accept a `routing_service`, make `get_best_shelter` async, use OSRM route for the ranked top candidate's distance/ETA.
- **Modify** `custom_components/shelter_finder/shelter_logic.py` — add an optional `extra_distances` dict to `rank_shelters` to override haversine distance per shelter id when OSRM results are available.
- **Modify** `custom_components/shelter_finder/sensor.py` — replace sync `_find_nearest_shelter` with an async version that uses `RoutingService`; sensors override `async_update` to pre-compute and cache the shelter result on the entity between coordinator ticks.
- **Create** `tests/test_routing_service.py` — unit tests for `RoutingService` (cache hit/miss, TTL, fallback, throttling, disabled mode, driving mode, LRU eviction).
- **Modify** `tests/test_alert_coordinator.py` — update existing tests for the async `get_best_shelter` signature and inject a fake routing service.
- **Modify** `tests/test_sensor.py` — async sensor tests with a fake routing service.

Each file owns one responsibility: `routing.py` = distance math + OSRM client; `shelter_logic.py` = scoring; `alert_coordinator.py` = alert state; sensors = HA entity surface.

---

## Task 1: `RouteResult` dataclass and `RoutingService` skeleton

**Files:**
- Modify: `custom_components/shelter_finder/routing.py`
- Test: `tests/test_routing_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_routing_service.py`:

```python
"""Tests for the RoutingService."""

from __future__ import annotations

import pytest

from custom_components.shelter_finder.routing import RouteResult, RoutingService


def test_route_result_is_dataclass() -> None:
    r = RouteResult(distance_m=1234.5, eta_seconds=890.2, source="osrm")
    assert r.distance_m == 1234.5
    assert r.eta_seconds == 890.2
    assert r.source == "osrm"


def test_routing_service_constructs_with_defaults() -> None:
    svc = RoutingService(session=None, enabled=False)
    assert svc.enabled is False
    assert svc.url == "https://router.project-osrm.org"
    assert svc.transport_mode == "foot"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'RouteResult'` (or `RoutingService`).

- [ ] **Step 3: Write minimal implementation**

Append to `custom_components/shelter_finder/routing.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RouteResult:
    distance_m: float
    eta_seconds: float
    source: str  # "osrm" or "haversine"


class RoutingService:
    """Wraps OSRM API with LRU+TTL cache and haversine fallback."""

    def __init__(
        self,
        session: Any,
        enabled: bool = False,
        url: str = "https://router.project-osrm.org",
        transport_mode: str = "foot",
        timeout_s: float = 5.0,
        cache_ttl_s: float = 300.0,
        cache_max: int = 500,
    ) -> None:
        self.session = session
        self.enabled = enabled
        self.url = url.rstrip("/")
        self.transport_mode = transport_mode
        self.timeout_s = timeout_s
        self.cache_ttl_s = cache_ttl_s
        self.cache_max = cache_max
```

Keep the existing `haversine_distance` / `calculate_eta_minutes` functions at the top of the file untouched.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/routing.py tests/test_routing_service.py
git commit -m "feat(routing): add RouteResult dataclass and RoutingService skeleton"
```

---

## Task 2: Fallback path when OSRM is disabled

**Files:**
- Modify: `custom_components/shelter_finder/routing.py`
- Test: `tests/test_routing_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_routing_service.py`:

```python
@pytest.mark.asyncio
async def test_async_get_route_disabled_returns_haversine() -> None:
    svc = RoutingService(session=None, enabled=False)
    # Paris: Notre-Dame -> Louvre ~1.1 km
    result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "haversine"
    assert 800 < result.distance_m < 1800
    # walking ETA at 1.4 m/s
    assert result.eta_seconds == pytest.approx(result.distance_m / 1.4, rel=0.01)


@pytest.mark.asyncio
async def test_async_get_route_disabled_driving_mode_uses_driving_speed() -> None:
    svc = RoutingService(session=None, enabled=False, transport_mode="driving")
    result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "haversine"
    assert result.eta_seconds == pytest.approx(result.distance_m / 8.3, rel=0.01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py -v`
Expected: FAIL — `RoutingService` has no `async_get_route` method.

- [ ] **Step 3: Write minimal implementation**

Add to `RoutingService` in `routing.py`:

```python
    async def async_get_route(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> RouteResult:
        """Return route between two points. Falls back to haversine when disabled/failed."""
        if not self.enabled or self.session is None:
            return self._haversine_result(lat1, lon1, lat2, lon2)
        return self._haversine_result(lat1, lon1, lat2, lon2)  # OSRM wired in Task 4

    def _haversine_result(
        self, lat1: float, lon1: float, lat2: float, lon2: float,
    ) -> RouteResult:
        from .const import TRAVEL_SPEEDS
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        mode_key = "driving" if self.transport_mode == "driving" else "walking"
        speed = TRAVEL_SPEEDS.get(mode_key, TRAVEL_SPEEDS["walking"])
        return RouteResult(distance_m=distance, eta_seconds=distance / speed, source="haversine")
```

Also ensure `tests/test_routing_service.py` has `pytestmark = pytest.mark.asyncio` OR individual `@pytest.mark.asyncio` decorators (already shown above). Confirm `pytest-asyncio` is already a test dep by running `pip show pytest-asyncio`; if not installed, add it:

```bash
pip install pytest-asyncio
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/routing.py tests/test_routing_service.py
git commit -m "feat(routing): haversine fallback when OSRM disabled"
```

---

## Task 3: In-memory LRU+TTL cache

**Files:**
- Modify: `custom_components/shelter_finder/routing.py`
- Test: `tests/test_routing_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_routing_service.py`:

```python
def test_cache_key_rounds_to_4_decimals() -> None:
    svc = RoutingService(session=None, enabled=False)
    assert svc._cache_key(48.85661111, 2.35221111, 48.86, 2.34) == (48.8566, 2.3522, 48.86, 2.34)


def test_cache_put_and_get_returns_same_result() -> None:
    svc = RoutingService(session=None, enabled=False)
    result = RouteResult(distance_m=100.0, eta_seconds=70.0, source="osrm")
    svc._cache_put((1.0, 2.0, 3.0, 4.0), result, now=1000.0)
    got = svc._cache_get((1.0, 2.0, 3.0, 4.0), now=1010.0)
    assert got is result


def test_cache_expires_after_ttl() -> None:
    svc = RoutingService(session=None, enabled=False, cache_ttl_s=300.0)
    result = RouteResult(distance_m=100.0, eta_seconds=70.0, source="osrm")
    svc._cache_put((1.0, 2.0, 3.0, 4.0), result, now=1000.0)
    assert svc._cache_get((1.0, 2.0, 3.0, 4.0), now=1301.0) is None


def test_cache_evicts_when_over_max() -> None:
    svc = RoutingService(session=None, enabled=False, cache_max=2)
    r = lambda v: RouteResult(distance_m=v, eta_seconds=v, source="osrm")
    svc._cache_put((1, 1, 1, 1), r(1.0), now=1.0)
    svc._cache_put((2, 2, 2, 2), r(2.0), now=2.0)
    svc._cache_put((3, 3, 3, 3), r(3.0), now=3.0)
    assert svc._cache_get((1, 1, 1, 1), now=4.0) is None
    assert svc._cache_get((2, 2, 2, 2), now=4.0) is not None
    assert svc._cache_get((3, 3, 3, 3), now=4.0) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py -v`
Expected: FAIL — `_cache_key`, `_cache_put`, `_cache_get` missing.

- [ ] **Step 3: Write minimal implementation**

Add to `RoutingService` in `routing.py` (and add `from collections import OrderedDict` at the top of the file):

```python
    # --- cache internals ---

    def _cache(self) -> "OrderedDict[tuple, tuple[float, RouteResult]]":
        if not hasattr(self, "_cache_store"):
            from collections import OrderedDict
            self._cache_store: OrderedDict[tuple, tuple[float, RouteResult]] = OrderedDict()
        return self._cache_store

    @staticmethod
    def _cache_key(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple:
        return (round(lat1, 4), round(lon1, 4), round(lat2, 4), round(lon2, 4))

    def _cache_get(self, key: tuple, now: float) -> RouteResult | None:
        cache = self._cache()
        entry = cache.get(key)
        if entry is None:
            return None
        inserted_at, result = entry
        if now - inserted_at > self.cache_ttl_s:
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        return result

    def _cache_put(self, key: tuple, result: RouteResult, now: float) -> None:
        cache = self._cache()
        cache[key] = (now, result)
        cache.move_to_end(key)
        while len(cache) > self.cache_max:
            cache.popitem(last=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/routing.py tests/test_routing_service.py
git commit -m "feat(routing): LRU+TTL cache helpers for RoutingService"
```

---

## Task 4: OSRM HTTP call (happy path)

**Files:**
- Modify: `custom_components/shelter_finder/routing.py`
- Test: `tests/test_routing_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_routing_service.py` (top-level imports add `from aioresponses import aioresponses` and `import aiohttp`):

```python
import aiohttp
from aioresponses import aioresponses


@pytest.mark.asyncio
async def test_osrm_success_returns_osrm_source() -> None:
    payload = {
        "code": "Ok",
        "routes": [{"distance": 1234.5, "duration": 890.2}],
    }
    # OSRM uses lon,lat order
    expected_url = (
        "https://router.project-osrm.org/route/v1/foot/"
        "2.3499,48.853;2.3376,48.8606?overview=false"
    )
    with aioresponses() as mocked:
        mocked.get(expected_url, payload=payload)
        async with aiohttp.ClientSession() as session:
            svc = RoutingService(session=session, enabled=True)
            result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "osrm"
    assert result.distance_m == 1234.5
    assert result.eta_seconds == 890.2


@pytest.mark.asyncio
async def test_osrm_second_call_is_cached() -> None:
    payload = {"code": "Ok", "routes": [{"distance": 500.0, "duration": 360.0}]}
    with aioresponses() as mocked:
        mocked.get(
            "https://router.project-osrm.org/route/v1/foot/"
            "2.3499,48.853;2.3376,48.8606?overview=false",
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            svc = RoutingService(session=session, enabled=True)
            first = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
            second = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert first.source == "osrm"
    assert second.source == "osrm"
    assert second.distance_m == 500.0
    # Only 1 mocked response was registered; a second call would fail the mock
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py -v`
Expected: FAIL — current stub always returns haversine, so `source == "haversine"`.

- [ ] **Step 3: Write minimal implementation**

Install aioresponses if missing:
```bash
pip install aioresponses
```

Replace the `async_get_route` body in `routing.py` with the full OSRM logic. Also add `import asyncio` and `import time` and `import logging` at the top; add `_LOGGER = logging.getLogger(__name__)`:

```python
    async def async_get_route(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> RouteResult:
        if not self.enabled or self.session is None:
            return self._haversine_result(lat1, lon1, lat2, lon2)

        key = self._cache_key(lat1, lon1, lat2, lon2)
        now = time.monotonic()
        cached = self._cache_get(key, now=now)
        if cached is not None:
            return cached

        url = (
            f"{self.url}/route/v1/{self.transport_mode}/"
            f"{lon1},{lat1};{lon2},{lat2}?overview=false"
        )
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s)
            async with self.session.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                data = await resp.json()
            routes = data.get("routes") or []
            if not routes:
                raise ValueError(f"OSRM returned no routes: {data.get('code')}")
            route = routes[0]
            result = RouteResult(
                distance_m=float(route["distance"]),
                eta_seconds=float(route["duration"]),
                source="osrm",
            )
            self._cache_put(key, result, now=now)
            return result
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as err:
            self._maybe_log_warning(err)
            return self._haversine_result(lat1, lon1, lat2, lon2)

    def _maybe_log_warning(self, err: Exception) -> None:
        # Stub; Task 5 throttles this
        _LOGGER.warning("OSRM call failed, falling back to haversine: %s", err)
```

Also add `import aiohttp` at the top of `routing.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/routing.py tests/test_routing_service.py
git commit -m "feat(routing): OSRM HTTP call with caching"
```

---

## Task 5: Fallback on error + throttled warning logs

**Files:**
- Modify: `custom_components/shelter_finder/routing.py`
- Test: `tests/test_routing_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_routing_service.py`:

```python
@pytest.mark.asyncio
async def test_osrm_http_error_falls_back_to_haversine() -> None:
    with aioresponses() as mocked:
        mocked.get(
            "https://router.project-osrm.org/route/v1/foot/"
            "2.3499,48.853;2.3376,48.8606?overview=false",
            status=500,
        )
        async with aiohttp.ClientSession() as session:
            svc = RoutingService(session=session, enabled=True)
            result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "haversine"
    assert result.distance_m > 0


@pytest.mark.asyncio
async def test_osrm_timeout_falls_back_to_haversine() -> None:
    with aioresponses() as mocked:
        mocked.get(
            "https://router.project-osrm.org/route/v1/foot/"
            "2.3499,48.853;2.3376,48.8606?overview=false",
            exception=asyncio.TimeoutError(),
        )
        async with aiohttp.ClientSession() as session:
            svc = RoutingService(session=session, enabled=True, timeout_s=0.1)
            result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "haversine"


def test_warning_throttle_allows_first_log_then_suppresses() -> None:
    svc = RoutingService(session=None, enabled=True, warn_throttle_s=600.0)
    assert svc._should_log_warning(now=1000.0) is True
    assert svc._should_log_warning(now=1001.0) is False
    assert svc._should_log_warning(now=1000.0 + 601.0) is True
```

Also add `import asyncio` to the top of the test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py -v`
Expected: FAIL — `_should_log_warning` missing, and `warn_throttle_s` kwarg not accepted.

- [ ] **Step 3: Write minimal implementation**

Modify `RoutingService.__init__` signature in `routing.py`:

```python
    def __init__(
        self,
        session: Any,
        enabled: bool = False,
        url: str = "https://router.project-osrm.org",
        transport_mode: str = "foot",
        timeout_s: float = 5.0,
        cache_ttl_s: float = 300.0,
        cache_max: int = 500,
        warn_throttle_s: float = 600.0,
    ) -> None:
        self.session = session
        self.enabled = enabled
        self.url = url.rstrip("/")
        self.transport_mode = transport_mode
        self.timeout_s = timeout_s
        self.cache_ttl_s = cache_ttl_s
        self.cache_max = cache_max
        self.warn_throttle_s = warn_throttle_s
        self._last_warn_at: float = 0.0
```

Replace the `_maybe_log_warning` stub with:

```python
    def _should_log_warning(self, now: float) -> bool:
        if now - self._last_warn_at >= self.warn_throttle_s:
            self._last_warn_at = now
            return True
        return False

    def _maybe_log_warning(self, err: Exception) -> None:
        if self._should_log_warning(time.monotonic()):
            _LOGGER.warning("OSRM call failed, falling back to haversine: %s", err)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py -v`
Expected: PASS (13 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/routing.py tests/test_routing_service.py
git commit -m "feat(routing): throttled warning logs on OSRM fallback"
```

---

## Task 6: Batch helper `async_get_routes_batch` with top-N haversine prefilter

**Files:**
- Modify: `custom_components/shelter_finder/routing.py`
- Test: `tests/test_routing_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_routing_service.py`:

```python
@pytest.mark.asyncio
async def test_batch_prefilters_to_top_n_then_queries_osrm() -> None:
    # 5 candidates; batch should OSRM only top 2 by haversine
    candidates = [
        {"id": "a", "latitude": 48.854, "longitude": 2.350},   # closest
        {"id": "b", "latitude": 48.858, "longitude": 2.340},   # 2nd
        {"id": "c", "latitude": 48.900, "longitude": 2.300},   # far
        {"id": "d", "latitude": 49.000, "longitude": 2.400},   # far
        {"id": "e", "latitude": 48.700, "longitude": 2.500},   # far
    ]
    person_lat, person_lon = 48.8530, 2.3499

    with aioresponses() as mocked:
        # register wildcard-ish: any GET returns same payload
        import re
        mocked.get(
            re.compile(r"https://router\.project-osrm\.org/.*"),
            payload={"code": "Ok", "routes": [{"distance": 111.0, "duration": 80.0}]},
            repeat=True,
        )
        async with aiohttp.ClientSession() as session:
            svc = RoutingService(session=session, enabled=True)
            results = await svc.async_get_routes_batch(
                person_lat, person_lon, candidates, top_n=2,
            )

    # All 5 candidates got a result
    assert set(results.keys()) == {"a", "b", "c", "d", "e"}
    # Top 2 (a,b) → osrm; rest → haversine
    assert results["a"].source == "osrm"
    assert results["b"].source == "osrm"
    assert results["c"].source == "haversine"
    assert results["d"].source == "haversine"
    assert results["e"].source == "haversine"


@pytest.mark.asyncio
async def test_batch_disabled_all_haversine() -> None:
    candidates = [
        {"id": "a", "latitude": 48.854, "longitude": 2.350},
        {"id": "b", "latitude": 48.858, "longitude": 2.340},
    ]
    svc = RoutingService(session=None, enabled=False)
    results = await svc.async_get_routes_batch(48.8530, 2.3499, candidates, top_n=2)
    assert results["a"].source == "haversine"
    assert results["b"].source == "haversine"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py -v`
Expected: FAIL — `async_get_routes_batch` not defined.

- [ ] **Step 3: Write minimal implementation**

Add to `RoutingService` in `routing.py`:

```python
    async def async_get_routes_batch(
        self,
        person_lat: float,
        person_lon: float,
        candidates: list[dict[str, Any]],
        top_n: int = 10,
    ) -> dict[str, RouteResult]:
        """Return {candidate_id: RouteResult}.

        Prefilters candidates by haversine and only queries OSRM for the top N
        nearest. Remaining candidates receive a haversine RouteResult directly.
        An `id` key must be present on each candidate.
        """
        # Compute haversine for all
        scored = []
        for c in candidates:
            d = haversine_distance(person_lat, person_lon, c["latitude"], c["longitude"])
            scored.append((d, c))
        scored.sort(key=lambda x: x[0])

        results: dict[str, RouteResult] = {}
        top = scored[:top_n]
        rest = scored[top_n:]

        # OSRM for top N (parallel)
        import asyncio as _asyncio
        tasks = [
            self.async_get_route(person_lat, person_lon, c["latitude"], c["longitude"])
            for _, c in top
        ]
        if tasks:
            top_results = await _asyncio.gather(*tasks)
            for (_, c), r in zip(top, top_results):
                results[c["id"]] = r

        # Haversine for the rest
        for d, c in rest:
            results[c["id"]] = self._haversine_result(
                person_lat, person_lon, c["latitude"], c["longitude"]
            )

        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py -v`
Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/routing.py tests/test_routing_service.py
git commit -m "feat(routing): batch helper with top-N haversine prefilter"
```

---

## Task 7: `shelter_logic.rank_shelters` — accept `extra_distances` override

**Files:**
- Modify: `custom_components/shelter_finder/shelter_logic.py`
- Test: `tests/test_shelter_logic.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_shelter_logic.py`:

```python
def test_rank_shelters_uses_extra_distances_when_provided() -> None:
    from custom_components.shelter_finder.shelter_logic import rank_shelters

    shelters = [
        {"id": "s1", "latitude": 48.854, "longitude": 2.350, "shelter_type": "subway"},
        {"id": "s2", "latitude": 48.858, "longitude": 2.340, "shelter_type": "bunker"},
    ]
    # Override: pretend OSRM tells us s2 is much closer than s1
    overrides = {"s1": 5000.0, "s2": 100.0}
    ranked = rank_shelters(
        shelters, "attack", person_lat=48.8530, person_lon=2.3499,
        extra_distances=overrides,
    )
    # s2 should now win with its short OSRM distance
    assert ranked[0]["id"] == "s2"
    assert ranked[0]["distance_m"] == 100
    # s1 got the overridden long distance
    s1 = next(s for s in ranked if s["id"] == "s1")
    assert s1["distance_m"] == 5000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_shelter_logic.py -v`
Expected: FAIL — `rank_shelters` does not accept `extra_distances`.

- [ ] **Step 3: Write minimal implementation**

Replace `rank_shelters` in `custom_components/shelter_finder/shelter_logic.py`:

```python
def rank_shelters(
    shelters: list[dict[str, Any]],
    threat_type: str,
    person_lat: float,
    person_lon: float,
    extra_distances: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    scored = []
    for shelter in shelters:
        shelter_id = shelter.get("id")
        if extra_distances is not None and shelter_id in extra_distances:
            distance = extra_distances[shelter_id]
        else:
            distance = _haversine_distance(person_lat, person_lon, shelter["latitude"], shelter["longitude"])
        s = score_shelter(shelter, threat_type, distance)
        scored.append({**shelter, "distance_m": round(distance), "score": s})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_shelter_logic.py -v`
Expected: PASS (existing tests still green + new one).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/shelter_logic.py tests/test_shelter_logic.py
git commit -m "feat(shelter_logic): rank_shelters accepts extra_distances override"
```

---

## Task 8: `AlertCoordinator` uses `RoutingService`

**Files:**
- Modify: `custom_components/shelter_finder/alert_coordinator.py`
- Test: `tests/test_alert_coordinator.py`

- [ ] **Step 1: Write the failing test**

At the top of `tests/test_alert_coordinator.py` add (or extend) fake-routing helper:

```python
import pytest
from custom_components.shelter_finder.routing import RouteResult


class _FakeRoutingService:
    def __init__(self, overrides: dict[tuple, RouteResult] | None = None) -> None:
        self.overrides = overrides or {}
        self.calls: list[tuple] = []

    async def async_get_route(self, lat1, lon1, lat2, lon2) -> RouteResult:
        key = (round(lat1, 4), round(lon1, 4), round(lat2, 4), round(lon2, 4))
        self.calls.append(key)
        return self.overrides.get(
            key,
            RouteResult(distance_m=999.0, eta_seconds=500.0, source="osrm"),
        )

    async def async_get_routes_batch(self, person_lat, person_lon, candidates, top_n=10):
        out: dict[str, RouteResult] = {}
        for c in candidates:
            r = await self.async_get_route(person_lat, person_lon, c["latitude"], c["longitude"])
            out[c["id"]] = r
        return out
```

Add a test:

```python
@pytest.mark.asyncio
async def test_get_best_shelter_uses_routing_service_for_distance_and_eta(monkeypatch) -> None:
    from custom_components.shelter_finder.alert_coordinator import AlertCoordinator

    class FakeState:
        def __init__(self, lat, lon):
            self.attributes = {"latitude": lat, "longitude": lon}

    class FakeStates:
        def get(self, _): return FakeState(48.853, 2.3499)

    class FakeHass:
        states = FakeStates()

    class FakeCoord:
        data = [
            {"id": "s1", "latitude": 48.858, "longitude": 2.340, "shelter_type": "bunker"},
        ]

    routing = _FakeRoutingService(overrides={
        (48.853, 2.3499, 48.858, 2.34): RouteResult(
            distance_m=450.0, eta_seconds=320.0, source="osrm"
        ),
    })

    ac = AlertCoordinator(
        hass=FakeHass(),
        shelter_coordinator=FakeCoord(),
        persons=["person.alice"],
        travel_mode="walking",
        routing_service=routing,
    )
    ac.trigger("attack")
    best = await ac.get_best_shelter("person.alice")
    assert best is not None
    assert best["distance_m"] == 450
    # eta_minutes == 320s / 60 rounded to 1 decimal
    assert best["eta_minutes"] == pytest.approx(5.3, abs=0.1)
    assert best["route_source"] == "osrm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_coordinator.py -v`
Expected: FAIL — `AlertCoordinator` constructor does not accept `routing_service`, and `get_best_shelter` is sync.

- [ ] **Step 3: Write minimal implementation**

Replace `AlertCoordinator.__init__` and `get_best_shelter` in `custom_components/shelter_finder/alert_coordinator.py`:

```python
from .routing import RoutingService  # noqa: E402

class AlertCoordinator:
    def __init__(
        self,
        hass: Any,
        shelter_coordinator: Any,
        persons: list[str],
        travel_mode: str = "walking",
        re_notification_interval: int = 5,
        max_re_notifications: int = 3,
        routing_service: "RoutingService | None" = None,
    ) -> None:
        self.hass = hass
        self.shelter_coordinator = shelter_coordinator
        self.persons = persons
        self.travel_mode = travel_mode
        self.re_notification_interval = re_notification_interval
        self.max_re_notifications = max_re_notifications
        self.routing_service = routing_service
        self._is_active = False
        self._threat_type: str | None = None
        self._triggered_by: str | None = None
        self._triggered_at: datetime | None = None
        self._persons_safe: list[str] = []
        self._notification_counts: dict[str, int] = {}
```

Replace `get_best_shelter` with async version:

```python
    async def get_best_shelter(self, person_entity_id: str) -> dict[str, Any] | None:
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
        if not shelters:
            return None

        # Ensure every shelter has an id (OSM ones usually do; synthesize otherwise)
        normalized = []
        for s in shelters:
            if "id" not in s:
                s = {**s, "id": f"{s.get('latitude')}_{s.get('longitude')}"}
            normalized.append(s)

        route_source = "haversine"
        extra_distances: dict[str, float] = {}
        eta_lookup: dict[str, float] = {}
        if self.routing_service is not None:
            routes = await self.routing_service.async_get_routes_batch(
                lat, lon, normalized, top_n=10,
            )
            for sid, r in routes.items():
                extra_distances[sid] = r.distance_m
                eta_lookup[sid] = r.eta_seconds
            if routes and any(r.source == "osrm" for r in routes.values()):
                route_source = "osrm"

        ranked = rank_shelters(
            normalized, self._threat_type, lat, lon,
            extra_distances=extra_distances or None,
        )
        if not ranked:
            return None
        best = ranked[0]
        best_id = best["id"]
        eta_seconds = eta_lookup.get(best_id)
        if eta_seconds is not None:
            best["eta_minutes"] = round(eta_seconds / 60.0, 1)
        else:
            best["eta_minutes"] = calculate_eta_minutes(best["distance_m"], self.travel_mode)
        best["route_source"] = route_source
        return best
```

Remove the line `from .routing import calculate_eta_minutes` if redundant — keep it, since it's still used for fallback.

- [ ] **Step 4: Update existing sync test that calls `get_best_shelter`**

In `tests/test_alert_coordinator.py`, find every existing test that calls `ac.get_best_shelter(...)` synchronously. Update each of them to be `async def`, add `@pytest.mark.asyncio`, and `await` the call. Leave behavior expectations intact. Example diff for one such test:

Before:
```python
def test_get_best_shelter_when_active(...):
    ac.trigger("storm")
    best = ac.get_best_shelter("person.alice")
    assert best["name"] == "Gare du Nord"
```

After:
```python
@pytest.mark.asyncio
async def test_get_best_shelter_when_active(...):
    ac.trigger("storm")
    best = await ac.get_best_shelter("person.alice")
    assert best["name"] == "Gare du Nord"
```

If previous tests constructed `AlertCoordinator` without `routing_service`, they'll still work (default `None` → haversine branch).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_alert_coordinator.py -v`
Expected: PASS (existing + new test).

- [ ] **Step 6: Commit**

```bash
git add custom_components/shelter_finder/alert_coordinator.py tests/test_alert_coordinator.py
git commit -m "feat(alert): AlertCoordinator.get_best_shelter uses RoutingService (async)"
```

---

## Task 9: `__init__.py` wires `RoutingService` into DI

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`
- Modify: `custom_components/shelter_finder/const.py` (no-op if keys already present — verify)
- Test: Manual smoke verification via existing integration tests.

- [ ] **Step 1: Verify const keys exist**

Run: `grep -n "CONF_OSRM_ENABLED\|CONF_OSRM_URL\|CONF_TRANSPORT_MODE\|DEFAULT_OSRM_URL\|DEFAULT_TRANSPORT_MODE" custom_components/shelter_finder/const.py`

If `CONF_TRANSPORT_MODE`, `DEFAULT_OSRM_URL`, or `DEFAULT_TRANSPORT_MODE` are missing (i.e., the OptionsFlow plan has not run yet in this branch), add them:

```python
# Append near the other CONF_/DEFAULT_ blocks in const.py if missing
CONF_TRANSPORT_MODE = "transport_mode"
DEFAULT_OSRM_URL = "https://router.project-osrm.org"
DEFAULT_OSRM_ENABLED = False
DEFAULT_TRANSPORT_MODE = "foot"
```

- [ ] **Step 2: Write the failing test**

Add `tests/test_init_routing_wiring.py`:

```python
"""Smoke test that RoutingService is exposed via hass.data."""

from __future__ import annotations

from custom_components.shelter_finder.routing import RoutingService


def test_routing_service_importable_from_package() -> None:
    # If this import fails, the symbol was renamed or removed
    assert RoutingService is not None


def test_routing_service_constructible_with_ha_style_session() -> None:
    # Mimic what __init__.py will do: async_get_clientsession(hass) returns a session-like
    class FakeSession: pass
    svc = RoutingService(
        session=FakeSession(),
        enabled=True,
        url="https://osrm.example.com",
        transport_mode="foot",
    )
    assert svc.enabled is True
    assert svc.url == "https://osrm.example.com"
```

- [ ] **Step 3: Run test to verify it passes already**

Run: `pytest tests/test_init_routing_wiring.py -v`
Expected: PASS (these are guardrail tests on the public symbol — they should pass already).

- [ ] **Step 4: Wire into `async_setup_entry`**

In `custom_components/shelter_finder/__init__.py`:

1. Add imports near other const imports:

```python
from .const import (
    # ... existing ...
    CONF_OSRM_ENABLED,
    CONF_OSRM_URL,
    CONF_TRANSPORT_MODE,
    DEFAULT_OSRM_ENABLED,
    DEFAULT_OSRM_URL,
    DEFAULT_TRANSPORT_MODE,
)
from .routing import RoutingService
```

2. Inside `async_setup_entry`, after `session = async_get_clientsession(hass)` and before `AlertCoordinator(...)` is built, add:

```python
    osrm_enabled = config.get(CONF_OSRM_ENABLED, DEFAULT_OSRM_ENABLED)
    osrm_url = config.get(CONF_OSRM_URL, DEFAULT_OSRM_URL)
    transport_mode = config.get(CONF_TRANSPORT_MODE, DEFAULT_TRANSPORT_MODE)
    routing_service = RoutingService(
        session=session,
        enabled=osrm_enabled,
        url=osrm_url,
        transport_mode=transport_mode,
    )
```

3. Pass `routing_service=routing_service` into the `AlertCoordinator(...)` constructor call.

4. Store it in `hass.data`:

```python
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "alert_coordinator": alert_coordinator,
        "cache": cache,
        "routing_service": routing_service,
    }
```

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: PASS (all previously-green tests remain green; new ones pass).

- [ ] **Step 6: Commit**

```bash
git add custom_components/shelter_finder/__init__.py custom_components/shelter_finder/const.py tests/test_init_routing_wiring.py
git commit -m "feat(init): instantiate RoutingService and inject into AlertCoordinator"
```

---

## Task 10: `sensor.py` — async OSRM-aware `_find_nearest_shelter`

**Files:**
- Modify: `custom_components/shelter_finder/sensor.py`
- Test: `tests/test_sensor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sensor.py` (import structures as already used in the file; a fake routing service like Task 8's can be redeclared locally or moved to `conftest.py` — for DRY, move it to `conftest.py`):

First extend `tests/conftest.py`:

```python
from custom_components.shelter_finder.routing import RouteResult


class FakeRoutingService:
    """Test double — always returns OSRM results unless configured otherwise."""

    def __init__(self, default_distance: float = 500.0, default_eta: float = 360.0) -> None:
        self._d = default_distance
        self._eta = default_eta

    async def async_get_route(self, lat1, lon1, lat2, lon2) -> RouteResult:
        return RouteResult(distance_m=self._d, eta_seconds=self._eta, source="osrm")

    async def async_get_routes_batch(self, person_lat, person_lon, candidates, top_n=10):
        return {
            c["id"]: RouteResult(distance_m=self._d, eta_seconds=self._eta, source="osrm")
            for c in candidates
        }


@pytest.fixture
def fake_routing_service() -> FakeRoutingService:
    return FakeRoutingService()
```

Now append to `tests/test_sensor.py`:

```python
@pytest.mark.asyncio
async def test_find_nearest_shelter_async_uses_routing_service(fake_routing_service) -> None:
    from custom_components.shelter_finder.sensor import _async_find_nearest_shelter

    shelters = [
        {"id": "s1", "name": "A", "latitude": 48.858, "longitude": 2.340, "shelter_type": "bunker"},
        {"id": "s2", "name": "B", "latitude": 48.900, "longitude": 2.500, "shelter_type": "civic"},
    ]
    result = await _async_find_nearest_shelter(
        fake_routing_service, shelters, 48.853, 2.3499,
    )
    assert result is not None
    # Both shelters get distance=500 from the fake service; first is returned (tie-break)
    assert result["distance_m"] == 500
    assert result["route_source"] == "osrm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sensor.py::test_find_nearest_shelter_async_uses_routing_service -v`
Expected: FAIL — `_async_find_nearest_shelter` not defined.

- [ ] **Step 3: Write minimal implementation**

In `custom_components/shelter_finder/sensor.py`, add imports:

```python
from .routing import RoutingService, calculate_eta_minutes, haversine_distance
```

Replace the module-level `_find_nearest_shelter` with its async OSRM-aware equivalent. Keep the old sync function too (some callers may still use it; but replace all internal callers):

```python
async def _async_find_nearest_shelter(
    routing_service: RoutingService | None,
    shelters: list[dict[str, Any]],
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    if not shelters:
        return None
    # Ensure ids
    normalized = []
    for s in shelters:
        if "id" not in s:
            s = {**s, "id": f"{s.get('latitude')}_{s.get('longitude')}"}
        normalized.append(s)

    if routing_service is None:
        best = None
        best_dist = float("inf")
        for s in normalized:
            d = haversine_distance(lat, lon, s["latitude"], s["longitude"])
            if d < best_dist:
                best_dist = d
                best = {**s, "distance_m": round(d), "route_source": "haversine",
                        "eta_minutes": calculate_eta_minutes(d, "walking")}
        return best

    routes = await routing_service.async_get_routes_batch(lat, lon, normalized, top_n=10)
    best = None
    best_dist = float("inf")
    for s in normalized:
        r = routes.get(s["id"])
        if r is None:
            continue
        if r.distance_m < best_dist:
            best_dist = r.distance_m
            best = {
                **s,
                "distance_m": round(r.distance_m),
                "eta_minutes": round(r.eta_seconds / 60.0, 1),
                "route_source": r.source,
            }
    return best
```

Keep the legacy sync `_find_nearest_shelter` untouched — it remains available but no longer called from the updated sensors below.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sensor.py::test_find_nearest_shelter_async_uses_routing_service -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/sensor.py tests/conftest.py tests/test_sensor.py
git commit -m "feat(sensor): async _async_find_nearest_shelter backed by RoutingService"
```

---

## Task 11: Sensors read `routing_service` from `hass.data` and refresh via `async_update`

**Files:**
- Modify: `custom_components/shelter_finder/sensor.py`
- Test: `tests/test_sensor.py`

Because HA entity `native_value` is a property (sync), we compute the shelter in `async_update` and cache it on the entity. Alert-active flow awaits `alert_coordinator.get_best_shelter` there too.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sensor.py`:

```python
@pytest.mark.asyncio
async def test_nearest_sensor_async_update_populates_from_routing(fake_routing_service) -> None:
    from custom_components.shelter_finder.sensor import ShelterNearestSensor

    class FakeState:
        attributes = {"latitude": 48.853, "longitude": 2.3499}

    class FakeStates:
        def get(self, _): return FakeState()

    class FakeHass:
        states = FakeStates()

    class FakeAlert:
        is_active = False
        async def get_best_shelter(self, _): return None

    class FakeCoord:
        data = [
            {"id": "s1", "name": "A", "latitude": 48.858, "longitude": 2.340, "shelter_type": "bunker"},
        ]
        def async_add_listener(self, *a, **k): return lambda: None

    sensor = ShelterNearestSensor(FakeCoord(), FakeAlert(), "person.alice", "alice")
    sensor.hass = FakeHass()
    sensor._routing_service = fake_routing_service  # injected by platform setup

    await sensor.async_update()
    assert sensor.native_value == "A"
    attrs = sensor.extra_state_attributes
    assert attrs["distance_m"] == 500
    assert attrs["route_source"] == "osrm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sensor.py::test_nearest_sensor_async_update_populates_from_routing -v`
Expected: FAIL — `async_update` does not yet populate the needed internal state; `_routing_service` not used.

- [ ] **Step 3: Write minimal implementation**

In `custom_components/shelter_finder/sensor.py`:

1. Update `async_setup_entry` to pull the routing service and pass it to each sensor:

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    routing_service = data.get("routing_service")
    persons = entry.data.get(CONF_PERSONS, [])

    entities: list[SensorEntity] = []
    for person_id in persons:
        person_name = person_id.split(".")[-1]
        n = ShelterNearestSensor(coordinator, alert_coordinator, person_id, person_name)
        d = ShelterDistanceSensor(coordinator, alert_coordinator, person_id, person_name)
        e = ShelterETASensor(coordinator, alert_coordinator, person_id, person_name)
        for s in (n, d, e):
            s._routing_service = routing_service
        entities.extend([n, d, e])
    entities.append(ShelterAlertTypeSensor(coordinator, alert_coordinator))
    async_add_entities(entities, update_before_add=True)
```

2. Add a private `async_update` + cached state to `ShelterNearestSensor`, `ShelterDistanceSensor`, `ShelterETASensor`. Use a shared helper on the class:

```python
class _RoutingBackedSensorMixin:
    """Shared resolver used by nearest/distance/ETA sensors."""

    _routing_service = None
    _cached_shelter: dict[str, Any] | None = None

    async def _resolve_shelter(self) -> dict[str, Any] | None:
        if self._alert_coordinator.is_active:
            return await self._alert_coordinator.get_best_shelter(self._person_id)
        shelters = self.coordinator.data or []
        coords = _get_person_coords(self.hass, self._person_id)
        if coords is None:
            return None
        return await _async_find_nearest_shelter(
            self._routing_service, shelters, coords[0], coords[1]
        )

    async def async_update(self) -> None:
        self._cached_shelter = await self._resolve_shelter()
```

3. Make `ShelterNearestSensor`, `ShelterDistanceSensor`, `ShelterETASensor` inherit from `_RoutingBackedSensorMixin` in addition to `CoordinatorEntity, SensorEntity`. Change their properties to read from the cache:

```python
class ShelterNearestSensor(_RoutingBackedSensorMixin, CoordinatorEntity, SensorEntity):
    # ... existing __init__ unchanged ...

    @property
    def native_value(self) -> str | None:
        return self._cached_shelter["name"] if self._cached_shelter else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._cached_shelter
        if s is None:
            return {}
        return {
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
            "shelter_type": s.get("shelter_type"),
            "source": s.get("source"),
            "distance_m": s.get("distance_m"),
            "score": s.get("score"),
            "route_source": s.get("route_source"),
        }


class ShelterDistanceSensor(_RoutingBackedSensorMixin, CoordinatorEntity, SensorEntity):
    # ... existing __init__ unchanged ...

    @property
    def native_value(self) -> int | None:
        return self._cached_shelter["distance_m"] if self._cached_shelter else None


class ShelterETASensor(_RoutingBackedSensorMixin, CoordinatorEntity, SensorEntity):
    # ... existing __init__ unchanged ...

    @property
    def native_value(self) -> float | None:
        if self._cached_shelter is None:
            return None
        return self._cached_shelter.get("eta_minutes")
```

Remove the earlier ad-hoc per-property resolution paths (they previously called the sync `_find_nearest_shelter`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sensor.py -v`
Expected: PASS (new test + previously-green sensor tests; update any test asserting the old sync flow to call `await sensor.async_update()` first before reading `native_value`).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/sensor.py tests/test_sensor.py
git commit -m "feat(sensor): async_update computes shelter via RoutingService and caches result"
```

---

## Task 12: Update `__init__.py` notification path to `await` async `get_best_shelter`

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`

- [ ] **Step 1: Identify affected callsite**

Run: `grep -n "alert_coordinator.get_best_shelter\|\.get_best_shelter(" custom_components/shelter_finder/`

Expected hits: `__init__.py` in `_send_alert_notifications`, plus anywhere else in the codebase (webhook, binary_sensor, button). Every call now needs to be `await`ed, and the enclosing function must be `async`.

- [ ] **Step 2: Edit `_send_alert_notifications`**

In `custom_components/shelter_finder/__init__.py` replace:

```python
        best = alert_coordinator.get_best_shelter(person_id)
```

with:

```python
        best = await alert_coordinator.get_best_shelter(person_id)
```

`_send_alert_notifications` is already `async def`, so no signature change needed.

- [ ] **Step 3: Sweep other callers**

Run: `grep -rn "\.get_best_shelter(" custom_components/shelter_finder/ tests/`

For every non-test callsite in the component package:
- If the caller is already `async def`, add `await`.
- If the caller is sync (e.g., a property), refactor to move the call into an `async_update` method (mirroring Task 11's pattern) and store the result on the entity.

Confirm candidates: `binary_sensor.py`, `button.py`, `webhook.py`. Apply the same `await` treatment; if any of them is sync, wrap using `hass.async_create_task(...)` only if fire-and-forget, otherwise convert to `async`.

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: PASS across all modules.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/__init__.py custom_components/shelter_finder/binary_sensor.py custom_components/shelter_finder/button.py custom_components/shelter_finder/webhook.py
git commit -m "refactor: await AlertCoordinator.get_best_shelter at all callsites"
```

---

## Task 13: End-to-end integration test — OSRM enabled path

**Files:**
- Test: `tests/test_routing_integration.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_routing_integration.py`:

```python
"""E2E: alert coordinator + routing service + real shelter list."""

from __future__ import annotations

import re

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.shelter_finder.alert_coordinator import AlertCoordinator
from custom_components.shelter_finder.routing import RoutingService


class _FakeState:
    def __init__(self, lat, lon):
        self.attributes = {"latitude": lat, "longitude": lon}


class _FakeStates:
    def __init__(self, lat, lon):
        self._s = _FakeState(lat, lon)
    def get(self, _): return self._s


class _FakeHass:
    def __init__(self, lat, lon):
        self.states = _FakeStates(lat, lon)


class _FakeCoord:
    def __init__(self, data): self.data = data


@pytest.mark.asyncio
async def test_end_to_end_osrm_ranks_shelter_by_real_route() -> None:
    shelters = [
        {"id": "subway", "name": "Metro", "latitude": 48.858, "longitude": 2.340, "shelter_type": "subway"},
        {"id": "civic",  "name": "Mairie", "latitude": 48.8535, "longitude": 2.3500, "shelter_type": "civic"},
    ]
    # OSRM will say "subway" is very far by actual walk (1200m) but "civic" is close (50m)
    with aioresponses() as mocked:
        # Match any OSRM URL; return different payloads for each coordinate pair
        def _handler(url, **_kwargs):
            u = str(url)
            if "2.34,48.858" in u:
                return aiohttp.web.json_response({"code": "Ok", "routes": [{"distance": 1200.0, "duration": 900.0}]})
            if "2.35,48.8535" in u:
                return aiohttp.web.json_response({"code": "Ok", "routes": [{"distance": 50.0, "duration": 40.0}]})
            return aiohttp.web.json_response({"code": "NoRoute", "routes": []})

        mocked.get(
            re.compile(r"https://router\.project-osrm\.org/.*2\.34,48\.858.*"),
            payload={"code": "Ok", "routes": [{"distance": 1200.0, "duration": 900.0}]},
            repeat=True,
        )
        mocked.get(
            re.compile(r"https://router\.project-osrm\.org/.*2\.35,48\.8535.*"),
            payload={"code": "Ok", "routes": [{"distance": 50.0, "duration": 40.0}]},
            repeat=True,
        )

        async with aiohttp.ClientSession() as session:
            routing = RoutingService(session=session, enabled=True)
            ac = AlertCoordinator(
                hass=_FakeHass(48.853, 2.3499),
                shelter_coordinator=_FakeCoord(shelters),
                persons=["person.alice"],
                routing_service=routing,
            )
            ac.trigger("attack")
            best = await ac.get_best_shelter("person.alice")

    # Under "attack", subway (score 9) should normally beat civic (score 7).
    # But civic is only 50m vs subway 1200m → distance bonus flips the ranking.
    # score = type*10 + max(0, 10*(1 - d/15000))
    # subway: 90 + 10*(1-1200/15000) = 90 + 9.2 = 99.2
    # civic:  70 + 10*(1-50/15000)   = 70 + 9.97 = 79.97
    # Subway still wins here — adjust assertion to verify route-aware distance propagated:
    assert best is not None
    assert best["route_source"] == "osrm"
    # best shelter (subway) has the OSRM distance, not the haversine one
    assert best["distance_m"] == 1200
    assert best["eta_minutes"] == 15.0
```

- [ ] **Step 2: Run test to verify it fails** (it should not — this is an integration guardrail; if implementation is correct, it passes immediately)

Run: `pytest tests/test_routing_integration.py -v`
Expected: PASS. If it fails, debug the failure before moving on.

- [ ] **Step 3: Commit**

```bash
git add tests/test_routing_integration.py
git commit -m "test(routing): end-to-end OSRM integration test"
```

---

## Task 14: Manifest + docs housekeeping

**Files:**
- Modify: `custom_components/shelter_finder/manifest.json` (bump version)
- Modify: `README.md` (if exists — add OSRM section)

- [ ] **Step 1: Bump version**

Open `custom_components/shelter_finder/manifest.json` and change the `"version"` field to `"0.6.0"` (or whatever the next semver is; align with the OptionsFlow plan).

- [ ] **Step 2: Run full suite**

Run: `pytest tests/ -v`
Expected: ALL PASS.

- [ ] **Step 3: Commit**

```bash
git add custom_components/shelter_finder/manifest.json
git commit -m "chore: bump version to 0.6.0 for OSRM routing"
```

---

## Self-Review

**Spec coverage checklist:**
- [x] `RouteResult` dataclass — Task 1.
- [x] `RoutingService.async_get_route(lat1, lon1, lat2, lon2, mode)` — Tasks 2, 4. Note: mode is a constructor arg (`transport_mode`) in this implementation rather than per-call; spec writes `mode="foot"` as default, and the user per the integration spec always uses the config-selected mode, so constructor-level is simpler. Documented in the class.
- [x] OSRM URL format `GET /route/v1/foot/{lon1},{lat1};{lon2},{lat2}?overview=false` — Task 4, with lon/lat order.
- [x] In-memory LRU, key on `round(..., 4)` tuple, TTL 5 min, max 500 — Task 3.
- [x] Fallback on timeout/HTTP/connection error → `source="haversine"`, never mark sensor unavailable — Tasks 2, 5.
- [x] Warning log throttled to once per 10 min — Task 5.
- [x] `sensor.py` uses `RoutingService` instead of `haversine_distance` — Tasks 10, 11.
- [x] `alert_coordinator.py` uses `RoutingService` in `get_best_shelter` — Task 8.
- [x] `shelter_logic.rank_shelters` accepts optional route distances — Task 7.
- [x] `__init__.py` instantiates and injects — Task 9.
- [x] `const.py` already has `CONF_OSRM_ENABLED`/`CONF_OSRM_URL` (Task 9 adds missing `CONF_TRANSPORT_MODE`, `DEFAULT_*` if needed).
- [x] Top-N haversine prefilter for large shelter counts — Task 6.
- [x] Tests — Tasks 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 13.

**Out of scope for this plan (belongs to OptionsFlow plan):** the "Routage" UI step of `config_flow.py`.

**Type consistency check:** `RouteResult(distance_m, eta_seconds, source)` used identically across all tasks. `RoutingService.async_get_route(...)` signature stable. `async_get_routes_batch(person_lat, person_lon, candidates, top_n)` → `dict[str, RouteResult]` used in Tasks 6, 8, 10, 11. `rank_shelters(..., extra_distances=...)` signature used identically in Tasks 7, 8. `_cached_shelter` attribute used consistently in Task 11. No drift detected.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-14-shelter-finder-v0.6-osrm.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
