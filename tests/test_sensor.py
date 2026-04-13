"""Tests for Shelter Finder sensor entities."""

from __future__ import annotations
from unittest.mock import MagicMock
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
    alert.get_best_shelter.return_value = None
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

def test_nearest_sensor_with_alert(mock_coordinator, mock_alert_coordinator):
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.get_best_shelter.return_value = {
        "name": "Best Bunker", "latitude": 48.856, "longitude": 2.352,
        "shelter_type": "bunker", "distance_m": 450, "eta_minutes": 5.4, "source": "osm", "score": 95.0,
    }
    sensor = ShelterNearestSensor(mock_coordinator, mock_alert_coordinator, "person.alice", "alice")
    assert sensor.native_value == "Best Bunker"
    attrs = sensor.extra_state_attributes
    assert attrs["shelter_type"] == "bunker"
    assert attrs["distance_m"] == 450
