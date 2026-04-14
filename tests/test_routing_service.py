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
