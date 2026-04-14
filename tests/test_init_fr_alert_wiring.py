"""Integration wiring tests for FR-Alert manager lifecycle."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import custom_components.shelter_finder as sf_init
from custom_components.shelter_finder import const


@pytest.mark.asyncio
async def test_build_alert_provider_manager_both_enabled():
    hass = MagicMock()
    hass.helpers = MagicMock()
    session = MagicMock()

    config = {
        const.CONF_PROVIDER_GEORISQUES: True,
        const.CONF_PROVIDER_METEO_FRANCE: True,
        const.CONF_PROVIDER_POLL_INTERVAL: 90,
        const.CONF_PROVIDER_ALERT_RADIUS_KM: 15,
        const.CONF_PROVIDER_AUTO_CANCEL: False,
        const.CONF_PROVIDER_MIN_SEVERITY: "moderate",
    }
    alert_coord = MagicMock()
    manager = sf_init._build_alert_provider_manager(
        hass=hass,
        session=session,
        config=config,
        alert_coordinator=alert_coord,
        trigger_callback=lambda: None,
    )

    assert manager is not None
    assert len(manager._providers) == 2
    assert manager._polling_interval == 90
    assert manager._radius_km == 15
    assert manager._auto_cancel is False
    assert manager._min_severity == "moderate"


@pytest.mark.asyncio
async def test_build_alert_provider_manager_none_enabled_returns_none():
    hass = MagicMock()
    session = MagicMock()
    config = {
        const.CONF_PROVIDER_GEORISQUES: False,
        const.CONF_PROVIDER_METEO_FRANCE: False,
    }
    manager = sf_init._build_alert_provider_manager(
        hass=hass,
        session=session,
        config=config,
        alert_coordinator=MagicMock(),
        trigger_callback=lambda: None,
    )
    assert manager is None


@pytest.mark.asyncio
async def test_build_alert_provider_manager_clamps_polling_interval():
    hass = MagicMock()
    session = MagicMock()
    config = {
        const.CONF_PROVIDER_GEORISQUES: True,
        const.CONF_PROVIDER_METEO_FRANCE: False,
        const.CONF_PROVIDER_POLL_INTERVAL: 5,   # below min
    }
    manager = sf_init._build_alert_provider_manager(
        hass=hass, session=session, config=config,
        alert_coordinator=MagicMock(), trigger_callback=lambda: None,
    )
    assert manager is not None
    assert manager._polling_interval == const.PROVIDER_POLL_INTERVAL_MIN

    config[const.CONF_PROVIDER_POLL_INTERVAL] = 9999
    manager2 = sf_init._build_alert_provider_manager(
        hass=hass, session=session, config=config,
        alert_coordinator=MagicMock(), trigger_callback=lambda: None,
    )
    assert manager2._polling_interval == const.PROVIDER_POLL_INTERVAL_MAX
