"""Integration test: _send_alert_notifications triggers TTS announce."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.shelter_finder import _send_alert_notifications
from custom_components.shelter_finder.const import DOMAIN


@pytest.mark.asyncio
async def test_send_alert_notifications_calls_tts_service_with_drill_flag() -> None:
    ac = MagicMock()
    ac.persons = ["person.alice"]
    ac.threat_type = "storm"
    ac.is_drill = True
    ac.get_best_shelter = AsyncMock(return_value={"name": "Ecole", "distance_m": 300, "eta_minutes": 4,
                                     "latitude": 48.8, "longitude": 2.3, "shelter_type": "school"})
    ac.record_notification = MagicMock()

    tts = MagicMock()
    tts.async_announce = AsyncMock()

    hass = MagicMock()
    hass.data = {DOMAIN: {"tts_service": tts}}
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_services = MagicMock(return_value={"notify": {}})
    hass.services.async_call = AsyncMock()

    await _send_alert_notifications(hass, ac, message="")

    tts.async_announce.assert_awaited_once()
    kwargs = tts.async_announce.await_args.kwargs
    assert kwargs["threat_type"] == "storm"
    assert kwargs["is_drill"] is True
    assert "person.alice" in kwargs["shelters_by_person"]


@pytest.mark.asyncio
async def test_send_alert_notifications_no_tts_service_does_not_raise() -> None:
    ac = MagicMock()
    ac.persons = []
    ac.threat_type = "flood"
    ac.is_drill = False

    hass = MagicMock()
    hass.data = {DOMAIN: {}}  # no tts_service
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_services = MagicMock(return_value={"notify": {}})
    hass.services.async_call = AsyncMock()

    # Must not raise.
    await _send_alert_notifications(hass, ac, message="")


@pytest.mark.asyncio
async def test_send_alert_notifications_tts_exception_is_swallowed(caplog) -> None:
    ac = MagicMock()
    ac.persons = []
    ac.threat_type = "flood"
    ac.is_drill = False
    ac.get_best_shelter = lambda p: None

    tts = MagicMock()
    tts.async_announce = AsyncMock(side_effect=RuntimeError("boom"))

    hass = MagicMock()
    hass.data = {DOMAIN: {"tts_service": tts}}
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_services = MagicMock(return_value={"notify": {}})
    hass.services.async_call = AsyncMock()

    with caplog.at_level("ERROR"):
        await _send_alert_notifications(hass, ac, message="")
    assert any("TTS announcement failed" in r.message for r in caplog.records)
