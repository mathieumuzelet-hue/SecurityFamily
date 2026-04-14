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
