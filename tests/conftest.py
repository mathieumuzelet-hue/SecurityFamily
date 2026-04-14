"""Fixtures for Shelter Finder tests."""

from __future__ import annotations

import pytest

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
