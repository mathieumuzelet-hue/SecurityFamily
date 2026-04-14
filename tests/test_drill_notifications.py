"""Tests for drill-mode service routing and notifications."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.shelter_finder import _register_services, _send_alert_notifications
from custom_components.shelter_finder.const import DOMAIN


@pytest.fixture
def mock_hass_with_ac():
    hass = MagicMock()
    hass.services = MagicMock()
    registered: dict[str, tuple] = {}

    def register(domain, name, handler, schema=None):
        registered[name] = (handler, schema)

    hass.services.async_register.side_effect = register
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_call = AsyncMock()
    hass.services.async_services = MagicMock(return_value={"notify": {"mobile_app_alice": None}})

    ac = MagicMock()
    ac.trigger = MagicMock()
    ac.cancel = MagicMock()
    ac.is_drill = False
    ac.threat_type = "storm"
    ac.persons = ["person.alice"]

    hass.data = {DOMAIN: {"alert_coordinator": ac}}
    hass._registered = registered
    hass._ac = ac
    return hass


@pytest.mark.asyncio
async def test_trigger_alert_service_passes_drill_true(mock_hass_with_ac):
    _register_services(mock_hass_with_ac)
    handler, schema = mock_hass_with_ac._registered["trigger_alert"]

    data = schema({"threat_type": "storm", "drill": True})
    call = MagicMock()
    call.data = data

    with patch("custom_components.shelter_finder._notify_coordinators"), \
         patch("custom_components.shelter_finder._send_alert_notifications", new=AsyncMock()):
        await handler(call)

    mock_hass_with_ac._ac.trigger.assert_called_once_with(
        "storm", triggered_by="service", drill=True
    )


@pytest.mark.asyncio
async def test_trigger_alert_service_defaults_drill_false(mock_hass_with_ac):
    _register_services(mock_hass_with_ac)
    handler, schema = mock_hass_with_ac._registered["trigger_alert"]

    data = schema({"threat_type": "storm"})
    call = MagicMock()
    call.data = data

    with patch("custom_components.shelter_finder._notify_coordinators"), \
         patch("custom_components.shelter_finder._send_alert_notifications", new=AsyncMock()):
        await handler(call)

    mock_hass_with_ac._ac.trigger.assert_called_once_with(
        "storm", triggered_by="service", drill=False
    )


def test_trigger_alert_schema_rejects_non_boolean_drill(mock_hass_with_ac):
    _register_services(mock_hass_with_ac)
    _, schema = mock_hass_with_ac._registered["trigger_alert"]
    with pytest.raises(vol.Invalid):
        schema({"threat_type": "storm", "drill": "maybe"})
