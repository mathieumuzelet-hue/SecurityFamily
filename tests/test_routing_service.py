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
