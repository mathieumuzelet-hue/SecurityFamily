"""Integration test: _send_alert_notifications triggers TTS announce."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.shelter_finder import _send_alert_notifications
from custom_components.shelter_finder.const import DOMAIN


def _make_hass_that_runs_tasks():
    """Return a MagicMock hass whose async_create_task actually awaits."""
    hass = MagicMock()
    loop = asyncio.get_event_loop()

    def _create_task(coro):
        return loop.create_task(coro)

    hass.async_create_task = MagicMock(side_effect=_create_task)
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_services = MagicMock(return_value={"notify": {}})
    hass.services.async_call = AsyncMock()
    return hass


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

    hass = _make_hass_that_runs_tasks()

    await _send_alert_notifications(hass, ac, message="", tts_service=tts)
    # TTS runs in a background task — give the loop a chance to run it.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

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

    hass = _make_hass_that_runs_tasks()

    # Must not raise.
    await _send_alert_notifications(hass, ac, message="", tts_service=None)


@pytest.mark.asyncio
async def test_send_alert_notifications_tts_exception_is_swallowed(caplog) -> None:
    ac = MagicMock()
    ac.persons = []
    ac.threat_type = "flood"
    ac.is_drill = False
    ac.get_best_shelter = AsyncMock(return_value=None)

    tts = MagicMock()
    tts.async_announce = AsyncMock(side_effect=RuntimeError("boom"))

    hass = _make_hass_that_runs_tasks()

    with caplog.at_level("ERROR"):
        await _send_alert_notifications(hass, ac, message="", tts_service=tts)
        # Let the background TTS task run and fail.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    assert any("TTS announcement failed" in r.message for r in caplog.records)
