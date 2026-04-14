"""Tests for Shelter Finder sensor entities."""

from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock
import pytest
from custom_components.shelter_finder.sensor import (
    ShelterAlertTypeSensor, ShelterDistanceSensor, ShelterETASensor, ShelterNearestSensor,
)

@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = [{"osm_id": "node/1", "name": "Abri Test", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker", "source": "osm"}]
    return coord

@pytest.fixture
def mock_alert_coordinator():
    alert = MagicMock()
    alert.is_active = False
    alert.threat_type = None
    alert.get_best_shelter = AsyncMock(return_value=None)
    return alert

def test_nearest_sensor_attributes(mock_coordinator, mock_alert_coordinator):
    sensor = ShelterNearestSensor(mock_coordinator, mock_alert_coordinator, "person.alice", "alice")
    assert sensor.unique_id == "shelter_finder_alice_nearest"
    assert sensor.name == "alice shelter nearest"

def test_distance_sensor_unit(mock_coordinator, mock_alert_coordinator):
    sensor = ShelterDistanceSensor(mock_coordinator, mock_alert_coordinator, "person.alice", "alice")
    assert sensor.native_unit_of_measurement == "m"

def test_eta_sensor_unit(mock_coordinator, mock_alert_coordinator):
    sensor = ShelterETASensor(mock_coordinator, mock_alert_coordinator, "person.alice", "alice")
    assert sensor.native_unit_of_measurement == "min"

def test_alert_type_sensor_no_alert(mock_coordinator, mock_alert_coordinator):
    sensor = ShelterAlertTypeSensor(mock_coordinator, mock_alert_coordinator)
    assert sensor.native_value == "none"

def test_alert_type_sensor_active(mock_coordinator, mock_alert_coordinator):
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.threat_type = "storm"
    sensor = ShelterAlertTypeSensor(mock_coordinator, mock_alert_coordinator)
    assert sensor.native_value == "storm"

@pytest.mark.asyncio
async def test_nearest_sensor_with_alert(mock_coordinator, mock_alert_coordinator):
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.get_best_shelter = AsyncMock(return_value={
        "name": "Best Bunker", "latitude": 48.856, "longitude": 2.352,
        "shelter_type": "bunker", "distance_m": 450, "eta_minutes": 5.4, "source": "osm", "score": 95.0,
    })
    sensor = ShelterNearestSensor(mock_coordinator, mock_alert_coordinator, "person.alice", "alice")
    await sensor.async_update()
    assert sensor.native_value == "Best Bunker"
    attrs = sensor.extra_state_attributes
    assert attrs["shelter_type"] == "bunker"
    assert attrs["distance_m"] == 450


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
