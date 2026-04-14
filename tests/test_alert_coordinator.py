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
    coord.search_radius = 2000
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


@pytest.mark.asyncio
async def test_get_best_shelter_does_not_mutate_cached_shelter_dicts() -> None:
    """Regression: get_best_shelter must not mutate coordinator's cached shelter dicts.

    Previously, writing eta_minutes / route_source to the ranked result would
    leak into self.shelter_coordinator.data and persist across alerts.
    """
    from custom_components.shelter_finder.alert_coordinator import AlertCoordinator

    class FakeState:
        def __init__(self, lat, lon):
            self.attributes = {"latitude": lat, "longitude": lon}

    class FakeStates:
        def get(self, _): return FakeState(48.853, 2.3499)

    class FakeHass:
        states = FakeStates()

    original_shelters = [
        {"id": "s1", "latitude": 48.858, "longitude": 2.340, "shelter_type": "bunker"},
    ]

    class FakeCoord:
        data = original_shelters

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
    # The returned dict has the enrichment keys.
    assert "eta_minutes" in best
    assert "route_source" in best
    # But the original cached shelter dict must NOT have been mutated.
    assert "eta_minutes" not in original_shelters[0]
    assert "route_source" not in original_shelters[0]

    # Call a second time (e.g. re-notification path) — the cached shelter
    # must still be untouched. This guards the B1 fix against a regression
    # where repeated enrichment could leak into the shared dict.
    best2 = await ac.get_best_shelter("person.alice")
    assert best2 is not None
    assert "eta_minutes" in best2
    assert "eta_minutes" not in original_shelters[0]
    assert "route_source" not in original_shelters[0]
    assert "distance_m" not in original_shelters[0]


# ---------------------------------------------------------------------------
# v0.6.3 — strict per-person distance cutoff before ranking
# ---------------------------------------------------------------------------

class _FakeState:
    def __init__(self, lat: float, lon: float) -> None:
        self.attributes = {"latitude": lat, "longitude": lon}


class _FakeStates:
    def __init__(self, state: _FakeState) -> None:
        self._state = state

    def get(self, _entity_id: str) -> _FakeState:
        return self._state


class _FakeHass:
    def __init__(self, state: _FakeState) -> None:
        self.states = _FakeStates(state)


class _FakeShelterCoord:
    def __init__(self, shelters: list[dict], search_radius: int = 2000) -> None:
        self.data = shelters
        self.search_radius = search_radius


@pytest.mark.asyncio
async def test_get_best_shelter_filters_distant_shelters() -> None:
    """A close mairie (civic, lower type-score) must beat a far metro (high type-score)."""
    # Person in central Paris (Hotel de Ville area).
    person_lat, person_lon = 48.8566, 2.3522

    # Close shelter ~500 m east: civic/mairie. For attack, civic=7 -> type*10=70.
    close_mairie = {
        "id": "close-mairie",
        "latitude": 48.8566,
        "longitude": 2.3590,  # ~500 m east
        "shelter_type": "civic",
    }
    # Far shelter ~22 km NW (Argenteuil/Cergy direction): subway.
    # For attack, subway=9 -> type*10=90; distance bonus is 0 past 15 km.
    # Without the cutoff this would win the ranking.
    far_metro = {
        "id": "far-metro",
        "latitude": 49.0470,  # ~22 km NW of Paris center
        "longitude": 2.2470,
        "shelter_type": "subway",
    }

    ac = AlertCoordinator(
        hass=_FakeHass(_FakeState(person_lat, person_lon)),
        shelter_coordinator=_FakeShelterCoord([close_mairie, far_metro], search_radius=2000),
        persons=["person.d"],
        travel_mode="walking",
    )
    ac.trigger("attack")
    best = await ac.get_best_shelter("person.d")
    assert best is not None
    assert best["id"] == "close-mairie", (
        f"expected the 500 m mairie but got {best['id']} "
        f"(distance_m={best.get('distance_m')})"
    )


@pytest.mark.asyncio
async def test_get_best_shelter_widens_when_too_few_in_initial_cutoff() -> None:
    """If <3 shelters within 1.5x radius, widen to 3x rather than returning None."""
    person_lat, person_lon = 48.8566, 2.3522
    # search_radius = 2000 m -> initial cutoff = 3000 m, widen = 6000 m.
    # One close shelter within 3 km, five more in the 3-6 km ring.
    shelters: list[dict] = [
        # within 3 km (~1.5 km east)
        {
            "id": "close-1",
            "latitude": 48.8566,
            "longitude": 2.3724,
            "shelter_type": "shelter",
        },
    ]
    # 5 shelters between 3 km and 6 km away (~4.5 km south).
    for i in range(5):
        shelters.append({
            "id": f"mid-{i}",
            "latitude": 48.8566 - 0.040 - i * 0.001,
            "longitude": 2.3522,
            "shelter_type": "bunker",
        })

    ac = AlertCoordinator(
        hass=_FakeHass(_FakeState(person_lat, person_lon)),
        shelter_coordinator=_FakeShelterCoord(shelters, search_radius=2000),
        persons=["person.a"],
        travel_mode="walking",
    )
    ac.trigger("attack")
    best = await ac.get_best_shelter("person.a")
    assert best is not None
    # After widening, all 6 candidates are in play; bunker (type=10) beats
    # plain shelter (type=3). We should get one of the "mid-*" shelters.
    assert best["id"].startswith("mid-"), (
        f"expected widened pool to be used, got {best['id']}"
    )


@pytest.mark.asyncio
async def test_get_best_shelter_returns_none_when_no_shelters_within_3x() -> None:
    """When every shelter is beyond 3x search_radius, return None."""
    person_lat, person_lon = 48.8566, 2.3522
    # search_radius = 2000 m -> 3x = 6000 m. Put all shelters ~22 km away.
    shelters = [
        {
            "id": f"far-{i}",
            "latitude": 49.0470 + i * 0.001,
            "longitude": 2.2470,
            "shelter_type": "bunker",
        }
        for i in range(3)
    ]

    ac = AlertCoordinator(
        hass=_FakeHass(_FakeState(person_lat, person_lon)),
        shelter_coordinator=_FakeShelterCoord(shelters, search_radius=2000),
        persons=["person.a"],
        travel_mode="walking",
    )
    ac.trigger("attack")
    best = await ac.get_best_shelter("person.a")
    assert best is None
