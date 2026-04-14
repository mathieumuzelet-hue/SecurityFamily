"""E2E: alert coordinator + routing service wired together.

Uses a stub RoutingService (not aioresponses) to avoid aiohttp thread/socket
leaks that pytest-homeassistant-custom-component's strict teardown detects.
The OSRM HTTP path is already covered by test_routing.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from custom_components.shelter_finder.alert_coordinator import AlertCoordinator


@dataclass
class _FakeRoute:
    distance_m: float
    eta_seconds: float
    source: str = "osrm"


class _StubRoutingService:
    def __init__(self, routes: dict[tuple[float, float, float, float], _FakeRoute]) -> None:
        self._routes = routes
        self.enabled = True

    async def async_get_route(self, lat1, lon1, lat2, lon2, **_kw):
        key = (round(lat1, 4), round(lon1, 4), round(lat2, 4), round(lon2, 4))
        return self._routes[key]

    async def async_get_routes_batch(self, lat1, lon1, shelters, top_n=10):
        out = {}
        for s in shelters[:top_n]:
            lat2 = s["latitude"]
            lon2 = s["longitude"]
            out[s["id"]] = await self.async_get_route(lat1, lon1, lat2, lon2)
        return out


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
    routes = {
        (48.853, 2.3499, 48.858, 2.34): _FakeRoute(distance_m=1200.0, eta_seconds=900.0),
        (48.853, 2.3499, 48.8535, 2.35): _FakeRoute(distance_m=50.0, eta_seconds=40.0),
    }
    routing = _StubRoutingService(routes)
    ac = AlertCoordinator(
        hass=_FakeHass(48.853, 2.3499),
        shelter_coordinator=_FakeCoord(shelters),
        persons=["person.alice"],
        routing_service=routing,
    )
    ac.trigger("attack")
    best = await ac.get_best_shelter("person.alice")

    assert best is not None
    assert best["route_source"] == "osrm"
    assert best["distance_m"] == 1200
    assert best["eta_minutes"] == 15.0
