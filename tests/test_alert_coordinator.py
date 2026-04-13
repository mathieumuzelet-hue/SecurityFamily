"""Tests for AlertCoordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.shelter_finder.alert_coordinator import AlertCoordinator


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

def test_get_best_shelter_for_person(alert_coord: AlertCoordinator, mock_hass: MagicMock) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    mock_state = MagicMock()
    mock_state.attributes = {"latitude": 48.857, "longitude": 2.351}
    mock_hass.states.get.return_value = mock_state
    result = alert_coord.get_best_shelter("person.alice")
    assert result is not None
    assert "name" in result
    assert "distance_m" in result
    assert "score" in result

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
