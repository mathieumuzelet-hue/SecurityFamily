"""Tests for Shelter Finder binary sensor."""

from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from custom_components.shelter_finder.binary_sensor import ShelterAlertBinarySensor

@pytest.fixture
def mock_coordinator():
    return MagicMock(data=[])

@pytest.fixture
def mock_alert_coordinator():
    alert = MagicMock()
    alert.is_active = False
    alert.threat_type = None
    alert.triggered_at = None
    alert.triggered_by = None
    alert.persons_safe = []
    return alert

def test_binary_sensor_off(mock_coordinator, mock_alert_coordinator):
    sensor = ShelterAlertBinarySensor(mock_coordinator, mock_alert_coordinator)
    assert sensor.is_on is False
    assert sensor.unique_id == "shelter_finder_alert"

def test_binary_sensor_on(mock_coordinator, mock_alert_coordinator):
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.threat_type = "storm"
    sensor = ShelterAlertBinarySensor(mock_coordinator, mock_alert_coordinator)
    assert sensor.is_on is True

def test_binary_sensor_attributes(mock_coordinator, mock_alert_coordinator):
    mock_alert_coordinator.is_active = True
    mock_alert_coordinator.threat_type = "attack"
    mock_alert_coordinator.triggered_by = "manual"
    mock_alert_coordinator.persons_safe = ["person.alice"]
    sensor = ShelterAlertBinarySensor(mock_coordinator, mock_alert_coordinator)
    attrs = sensor.extra_state_attributes
    assert attrs["threat_type"] == "attack"
    assert attrs["triggered_by"] == "manual"
    assert attrs["persons_safe"] == ["person.alice"]
