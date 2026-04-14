"""Tests for Shelter Finder webhook handler."""

from __future__ import annotations
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from custom_components.shelter_finder.webhook import async_handle_webhook

@pytest.fixture
def mock_hass():
    hass = MagicMock()
    alert_coord = MagicMock()
    alert_coord.trigger = MagicMock()
    # Per-entry layout: hass.data[DOMAIN][entry_id] = {...}. The webhook
    # now iterates entries and triggers each that has an alert_coordinator.
    hass.data = {"shelter_finder": {"entry_1": {"alert_coordinator": alert_coord}}}
    return hass

@pytest.fixture
def mock_request():
    request = AsyncMock()
    return request

@pytest.mark.asyncio
async def test_webhook_valid_payload(mock_hass):
    request = AsyncMock()
    request.json = AsyncMock(return_value={"threat_type": "storm", "source": "fr-alert"})
    response = await async_handle_webhook(mock_hass, "test", request)
    assert response.status == 200
    mock_hass.data["shelter_finder"]["entry_1"]["alert_coordinator"].trigger.assert_called_once_with("storm", triggered_by="webhook:fr-alert")

@pytest.mark.asyncio
async def test_webhook_invalid_threat_type(mock_hass):
    request = AsyncMock()
    request.json = AsyncMock(return_value={"threat_type": "zombie"})
    response = await async_handle_webhook(mock_hass, "test", request)
    assert response.status == 400

@pytest.mark.asyncio
async def test_webhook_missing_threat_type(mock_hass):
    request = AsyncMock()
    request.json = AsyncMock(return_value={"message": "test"})
    response = await async_handle_webhook(mock_hass, "test", request)
    assert response.status == 400

@pytest.mark.asyncio
async def test_webhook_with_optional_message(mock_hass):
    request = AsyncMock()
    request.json = AsyncMock(return_value={"threat_type": "attack", "message": "Alerte attentat"})
    response = await async_handle_webhook(mock_hass, "test", request)
    assert response.status == 200
