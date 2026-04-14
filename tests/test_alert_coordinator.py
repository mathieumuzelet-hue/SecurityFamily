"""Tests for AlertCoordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.shelter_finder.alert_coordinator import AlertCoordinator
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


@pytest.fixture
def mock_hass() -> MagicMock:
    hass = MagicMock()
    hass.states = MagicMock()
    return hass

@pytest.fixture
def mock_shelter_coordinator() -> MagicMock:
    coord = MagicMock()
    coord.data = [
        {"osm_id": "node/1", "name": "Abri A", "latitude": 48.856, "longitude": 2.352, "shelter_type": "bunker", "source": "osm"},
        {"osm_id": "node/2", "name": "Abri B", "latitude": 48.860, "longitude": 2.340, "shelter_type": "subway", "source": "osm"},
    ]
    return coord

@pytest.fixture
def alert_coord(mock_hass: MagicMock, mock_shelter_coordinator: MagicMock) -> AlertCoordinator:
    return AlertCoordinator(
        hass=mock_hass,
        shelter_coordinator=mock_shelter_coordinator,
        persons=["person.alice", "person.bob"],
        travel_mode="walking",
        re_notification_interval=5,
        max_re_notifications=3,
    )

def test_initial_state(alert_coord: AlertCoordinator) -> None:
    assert alert_coord.is_active is False
    assert alert_coord.threat_type is None
    assert alert_coord.persons_safe == []

def test_trigger_alert(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    assert alert_coord.is_active is True
    assert alert_coord.threat_type == "storm"
    assert alert_coord.triggered_by == "manual"
    assert alert_coord.triggered_at is not None

def test_cancel_alert(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    alert_coord.cancel()
    assert alert_coord.is_active is False
    assert alert_coord.threat_type is None
    assert alert_coord.persons_safe == []

def test_confirm_safe(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    alert_coord.confirm_safe("person.alice")
    assert "person.alice" in alert_coord.persons_safe

def test_confirm_safe_no_duplicate(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    alert_coord.confirm_safe("person.alice")
    alert_coord.confirm_safe("person.alice")
    assert alert_coord.persons_safe.count("person.alice") == 1

def test_confirm_safe_when_no_alert(alert_coord: AlertCoordinator) -> None:
    alert_coord.confirm_safe("person.alice")
    assert alert_coord.persons_safe == []

def test_all_safe_property(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    assert alert_coord.all_safe is False
    alert_coord.confirm_safe("person.alice")
    assert alert_coord.all_safe is False
    alert_coord.confirm_safe("person.bob")
    assert alert_coord.all_safe is True

@pytest.mark.asyncio
async def test_get_best_shelter_for_person(alert_coord: AlertCoordinator, mock_hass: MagicMock) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    mock_state = MagicMock()
    mock_state.attributes = {"latitude": 48.857, "longitude": 2.351}
    mock_hass.states.get.return_value = mock_state
    result = await alert_coord.get_best_shelter("person.alice")
    assert result is not None
    assert "name" in result
    assert "distance_m" in result
    assert "score" in result


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

def test_trigger_invalid_threat_type(alert_coord: AlertCoordinator) -> None:
    with pytest.raises(ValueError, match="Unknown threat type"):
        alert_coord.trigger("zombie_apocalypse", triggered_by="manual")

def test_should_re_notify(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    assert alert_coord.should_re_notify("person.alice") is True
    alert_coord.record_notification("person.alice")
    alert_coord.record_notification("person.alice")
    alert_coord.record_notification("person.alice")
    assert alert_coord.should_re_notify("person.alice") is False

def test_should_not_re_notify_safe_person(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    alert_coord.confirm_safe("person.alice")
    assert alert_coord.should_re_notify("person.alice") is False

def test_trigger_default_is_not_drill(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    assert alert_coord.is_drill is False

def test_trigger_with_drill_true(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual", drill=True)
    assert alert_coord.is_active is True
    assert alert_coord.is_drill is True
    assert alert_coord.threat_type == "storm"

def test_cancel_clears_drill_flag(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual", drill=True)
    alert_coord.cancel()
    assert alert_coord.is_drill is False

def test_retrigger_real_after_drill_resets_flag(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual", drill=True)
    alert_coord.cancel()
    alert_coord.trigger("flood", triggered_by="manual")
    assert alert_coord.is_drill is False
