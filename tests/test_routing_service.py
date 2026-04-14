"""Tests for the RoutingService.

OSRM HTTP path uses a fake session (not aiohttp.ClientSession + aioresponses)
to avoid aiohttp's threaded DNS resolver leaking into pytest-homeassistant-
custom-component's strict verify_cleanup teardown fixture.
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import pytest

from custom_components.shelter_finder.routing import RouteResult, RoutingService


# --- Fake session that mimics aiohttp.ClientSession.get(...) ---


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        payload: Any = None,
    ) -> None:
        self.status = status
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status >= 400:
            # aiohttp.ClientError is what routing.py catches; use the base class
            # to avoid ClientResponseError's strict request_info requirement.
            raise aiohttp.ClientError(f"HTTP {self.status}")

    async def json(self) -> Any:
        return self._payload


class _FakeGetCtx:
    def __init__(self, response: _FakeResponse | None, exc: BaseException | None) -> None:
        self._response = response
        self._exc = exc

    async def __aenter__(self) -> _FakeResponse:
        if self._exc is not None:
            raise self._exc
        assert self._response is not None
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSession:
    """Minimal stand-in for aiohttp.ClientSession, keyed by exact URL.

    Each entry can be a payload (200 OK), a status (error), or an exception to raise.
    Use `repeat=True` to allow infinite reuse of an entry (for batch tests).
    """

    def __init__(self) -> None:
        # list of (url_or_predicate, handler_dict, repeat)
        self._routes: list[tuple[Any, dict, bool]] = []
        self.calls: list[str] = []

    def add(
        self,
        url,
        *,
        payload: Any = None,
        status: int = 200,
        exception: BaseException | None = None,
        repeat: bool = False,
    ) -> None:
        self._routes.append(
            (url, {"payload": payload, "status": status, "exception": exception}, repeat),
        )

    def get(self, url: str, *_, **__) -> _FakeGetCtx:
        self.calls.append(url)
        for i, (pattern, handler, repeat) in enumerate(self._routes):
            matches = (
                pattern == url
                if isinstance(pattern, str)
                else bool(pattern.search(url))
            )
            if matches:
                if not repeat:
                    self._routes.pop(i)
                return _FakeGetCtx(
                    response=(
                        None
                        if handler["exception"] is not None
                        else _FakeResponse(status=handler["status"], payload=handler["payload"])
                    ),
                    exc=handler["exception"],
                )
        raise AssertionError(f"Unexpected URL called: {url}")


# --- Pure / cache / defaults tests (no HTTP) ---


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


@pytest.mark.asyncio
async def test_async_get_route_disabled_returns_haversine() -> None:
    svc = RoutingService(session=None, enabled=False)
    result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "haversine"
    assert 800 < result.distance_m < 1800
    assert result.eta_seconds == pytest.approx(result.distance_m / 1.4, rel=0.01)


@pytest.mark.asyncio
async def test_async_get_route_disabled_driving_mode_uses_driving_speed() -> None:
    svc = RoutingService(session=None, enabled=False, transport_mode="driving")
    result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "haversine"
    assert result.eta_seconds == pytest.approx(result.distance_m / 8.3, rel=0.01)


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


# --- OSRM HTTP path via fake session ---


EXPECTED_URL = (
    "https://router.project-osrm.org/route/v1/foot/"
    "2.3499,48.853;2.3376,48.8606?overview=false"
)


@pytest.mark.asyncio
async def test_osrm_success_returns_osrm_source() -> None:
    session = _FakeSession()
    session.add(
        EXPECTED_URL,
        payload={"code": "Ok", "routes": [{"distance": 1234.5, "duration": 890.2}]},
    )
    svc = RoutingService(session=session, enabled=True)
    result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "osrm"
    assert result.distance_m == 1234.5
    assert result.eta_seconds == 890.2
    assert session.calls == [EXPECTED_URL]


@pytest.mark.asyncio
async def test_osrm_second_call_is_cached() -> None:
    session = _FakeSession()
    # Register exactly once (no repeat). Second call must hit cache, not session.
    session.add(
        EXPECTED_URL,
        payload={"code": "Ok", "routes": [{"distance": 500.0, "duration": 360.0}]},
    )
    svc = RoutingService(session=session, enabled=True)
    first = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    second = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert first.source == "osrm"
    assert second.source == "osrm"
    assert second.distance_m == 500.0
    assert len(session.calls) == 1  # cache hit prevented a 2nd HTTP call


@pytest.mark.asyncio
async def test_osrm_http_error_falls_back_to_haversine() -> None:
    session = _FakeSession()
    session.add(EXPECTED_URL, status=500)
    svc = RoutingService(session=session, enabled=True)
    result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "haversine"
    assert result.distance_m > 0


@pytest.mark.asyncio
async def test_osrm_timeout_falls_back_to_haversine() -> None:
    session = _FakeSession()
    session.add(EXPECTED_URL, exception=asyncio.TimeoutError())
    svc = RoutingService(session=session, enabled=True, timeout_s=0.1)
    result = await svc.async_get_route(48.8530, 2.3499, 48.8606, 2.3376)
    assert result.source == "haversine"


def test_warning_throttle_allows_first_log_then_suppresses() -> None:
    svc = RoutingService(session=None, enabled=True, warn_throttle_s=600.0)
    assert svc._should_log_warning(now=1000.0) is True
    assert svc._should_log_warning(now=1001.0) is False
    assert svc._should_log_warning(now=1000.0 + 601.0) is True


@pytest.mark.asyncio
async def test_batch_prefilters_to_top_n_then_queries_osrm() -> None:
    candidates = [
        {"id": "a", "latitude": 48.854, "longitude": 2.350},   # closest
        {"id": "b", "latitude": 48.858, "longitude": 2.340},   # 2nd
        {"id": "c", "latitude": 48.900, "longitude": 2.300},   # far
        {"id": "d", "latitude": 49.000, "longitude": 2.400},   # far
        {"id": "e", "latitude": 48.700, "longitude": 2.500},   # far
    ]
    person_lat, person_lon = 48.8530, 2.3499

    import re

    session = _FakeSession()
    session.add(
        re.compile(r"https://router\.project-osrm\.org/.*"),
        payload={"code": "Ok", "routes": [{"distance": 111.0, "duration": 80.0}]},
        repeat=True,
    )
    svc = RoutingService(session=session, enabled=True)
    results = await svc.async_get_routes_batch(
        person_lat, person_lon, candidates, top_n=2,
    )

    assert set(results.keys()) == {"a", "b", "c", "d", "e"}
    assert results["a"].source == "osrm"
    assert results["b"].source == "osrm"
    assert results["c"].source == "haversine"
    assert results["d"].source == "haversine"
    assert results["e"].source == "haversine"
    # Exactly top_n=2 HTTP calls
    assert len(session.calls) == 2


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
