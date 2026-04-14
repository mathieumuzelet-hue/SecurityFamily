"""Tests for the multi-step OptionsFlow of Shelter Finder v0.6."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.shelter_finder.config_flow import ShelterFinderOptionsFlow
from custom_components.shelter_finder.const import (
    CONF_ADAPTIVE_RADIUS,
    CONF_CACHE_TTL,
    CONF_PROVIDER_ALERT_RADIUS_KM,
    CONF_PROVIDER_AUTO_CANCEL,
    CONF_PROVIDER_GEORISQUES,
    CONF_PROVIDER_METEO_FRANCE,
    CONF_PROVIDER_MIN_SEVERITY,
    CONF_PROVIDER_POLL_INTERVAL,
    CONF_RE_NOTIFICATION_INTERVAL,
    CONF_SEARCH_RADIUS,
)
from tests.stubs.homeassistant.config_entries import ConfigEntry


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_flow(data=None, options=None) -> ShelterFinderOptionsFlow:
    entry = ConfigEntry(data=data or {}, options=options or {})
    return ShelterFinderOptionsFlow(entry)


def test_step_init_renders_sources_and_radius_fields() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_init())

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema.keys()}
    for expected in (
        CONF_SEARCH_RADIUS,
        CONF_ADAPTIVE_RADIUS,
        CONF_CACHE_TTL,
        CONF_PROVIDER_GEORISQUES,
        CONF_PROVIDER_METEO_FRANCE,
        CONF_PROVIDER_POLL_INTERVAL,
        CONF_PROVIDER_MIN_SEVERITY,
        CONF_PROVIDER_AUTO_CANCEL,
        CONF_PROVIDER_ALERT_RADIUS_KM,
    ):
        assert expected in schema_keys, f"missing field {expected}"


def test_step_init_submit_advances_to_routing() -> None:
    flow = _make_flow()
    # Prime the flow so _current() works (it does not need the first form render,
    # but we call it to mirror real HA behaviour).
    _run(flow.async_step_init())

    result = _run(flow.async_step_init(user_input={
        CONF_SEARCH_RADIUS: 3000,
        CONF_ADAPTIVE_RADIUS: True,
        CONF_CACHE_TTL: 12,
        CONF_PROVIDER_GEORISQUES: True,
        CONF_PROVIDER_METEO_FRANCE: False,
        CONF_PROVIDER_POLL_INTERVAL: 90,
        CONF_PROVIDER_MIN_SEVERITY: "moderate",
        CONF_PROVIDER_AUTO_CANCEL: True,
        CONF_PROVIDER_ALERT_RADIUS_KM: 20,
    }))

    assert result["type"] == "form"
    assert result["step_id"] == "routing"
    # Submitted values must be persisted on the flow for the final create_entry.
    assert flow._options[CONF_PROVIDER_GEORISQUES] is True
    assert flow._options[CONF_PROVIDER_POLL_INTERVAL] == 90


from custom_components.shelter_finder.const import (
    CONF_OSRM_ENABLED,
    CONF_OSRM_MODE,
    CONF_OSRM_TRANSPORT_MODE,
    CONF_OSRM_URL,
)


def test_step_routing_renders_all_osrm_fields() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_routing())

    assert result["type"] == "form"
    assert result["step_id"] == "routing"
    schema_keys = {str(k) for k in result["data_schema"].schema.keys()}
    for expected in (
        CONF_OSRM_ENABLED,
        CONF_OSRM_MODE,
        CONF_OSRM_URL,
        CONF_OSRM_TRANSPORT_MODE,
    ):
        assert expected in schema_keys, f"missing field {expected}"


def test_step_routing_submit_advances_to_notifications() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_routing(user_input={
        CONF_OSRM_ENABLED: True,
        CONF_OSRM_MODE: "self_hosted",
        CONF_OSRM_URL: "http://osrm.local:5000",
        CONF_OSRM_TRANSPORT_MODE: "walking",
    }))

    assert result["type"] == "form"
    assert result["step_id"] == "notifications"
    assert flow._options[CONF_OSRM_ENABLED] is True
    assert flow._options[CONF_OSRM_MODE] == "self_hosted"
    assert flow._options[CONF_OSRM_URL] == "http://osrm.local:5000"


from custom_components.shelter_finder.const import (
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_TTS_ENABLED,
    CONF_TTS_MEDIA_PLAYERS,
    CONF_TTS_SERVICE,
    CONF_TTS_VOLUME,
)


def test_step_notifications_renders_renotif_and_tts_fields() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_notifications())

    assert result["type"] == "form"
    assert result["step_id"] == "notifications"
    schema_keys = {str(k) for k in result["data_schema"].schema.keys()}
    for expected in (
        CONF_RE_NOTIFICATION_INTERVAL,
        CONF_MAX_RE_NOTIFICATIONS,
        CONF_TTS_ENABLED,
        CONF_TTS_SERVICE,
        CONF_TTS_MEDIA_PLAYERS,
        CONF_TTS_VOLUME,
    ):
        assert expected in schema_keys, f"missing field {expected}"


def test_step_notifications_submit_advances_to_advanced() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_notifications(user_input={
        CONF_RE_NOTIFICATION_INTERVAL: 10,
        CONF_MAX_RE_NOTIFICATIONS: 5,
        CONF_TTS_ENABLED: True,
        CONF_TTS_SERVICE: "tts.google_translate_say",
        CONF_TTS_MEDIA_PLAYERS: ["media_player.living_room", "media_player.kitchen"],
        CONF_TTS_VOLUME: 70,
    }))

    assert result["type"] == "form"
    assert result["step_id"] == "advanced"
    assert flow._options[CONF_TTS_ENABLED] is True
    assert flow._options[CONF_TTS_VOLUME] == 70
    assert flow._options[CONF_TTS_MEDIA_PLAYERS] == [
        "media_player.living_room",
        "media_player.kitchen",
    ]
