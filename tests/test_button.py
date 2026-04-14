"""Tests for Shelter Finder button entities."""

from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from custom_components.shelter_finder.button import ShelterTriggerAlertButton, ShelterCancelAlertButton

@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = [{"name": "Test", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter"}]
    coord.async_set_updated_data = MagicMock()
    return coord

@pytest.fixture
def mock_alert_coordinator():
    alert = MagicMock()
    alert.trigger = MagicMock()
    alert.cancel = MagicMock()
    alert.is_active = False
    return alert

def test_trigger_button_attributes(mock_coordinator, mock_alert_coordinator):
    button = ShelterTriggerAlertButton(mock_coordinator, mock_alert_coordinator)
    assert button.unique_id == "shelter_finder_trigger_alert"
    assert "alert" in button.icon

def test_cancel_button_attributes(mock_coordinator, mock_alert_coordinator):
    button = ShelterCancelAlertButton(mock_coordinator, mock_alert_coordinator)
    assert button.unique_id == "shelter_finder_cancel_alert"

@pytest.mark.asyncio
async def test_trigger_button_press(mock_coordinator, mock_alert_coordinator):
    button = ShelterTriggerAlertButton(mock_coordinator, mock_alert_coordinator)
    await button.async_press()
    mock_alert_coordinator.trigger.assert_called_once_with("storm", triggered_by="button")
    mock_coordinator.async_set_updated_data.assert_called_once()

@pytest.mark.asyncio
async def test_cancel_button_press(mock_coordinator, mock_alert_coordinator):
    button = ShelterCancelAlertButton(mock_coordinator, mock_alert_coordinator)
    await button.async_press()
    mock_alert_coordinator.cancel.assert_called_once()
    mock_coordinator.async_set_updated_data.assert_called_once()


from custom_components.shelter_finder.button import ShelterDrillButton


def test_drill_button_attributes(mock_coordinator, mock_alert_coordinator):
    button = ShelterDrillButton(mock_coordinator, mock_alert_coordinator)
    assert button.unique_id == "shelter_finder_drill_alert"
    assert "alert" in button.icon or "practice" in button.icon or "school" in button.icon


@pytest.mark.asyncio
async def test_drill_button_press(mock_coordinator, mock_alert_coordinator):
    button = ShelterDrillButton(mock_coordinator, mock_alert_coordinator)
    await button.async_press()
    mock_alert_coordinator.trigger.assert_called_once_with(
        "storm", triggered_by="button", drill=True
    )
    mock_coordinator.async_set_updated_data.assert_called_once()
