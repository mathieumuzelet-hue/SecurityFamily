"""Tests for AlertProviderManager orchestration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.shelter_finder.alert_provider_manager import (
    AlertProviderManager,
)
from custom_components.shelter_finder.alert_providers.base import (
    AlertProvider,
    GouvAlert,
)


class _FakeProvider(AlertProvider):
    source_name = "fake"

    def __init__(self, alerts: list[GouvAlert]):
        self._alerts = alerts
        self.calls = 0

    async def async_fetch_alerts(self, lat, lon, radius_km):
        self.calls += 1
        return list(self._alerts)


class _FakeCoordinator:
    def __init__(self):
        self._active = False
        self._threat: str | None = None
        self._by: str | None = None
        self.trigger_calls: list[tuple[str, str]] = []
        self.cancel_calls = 0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def triggered_by(self) -> str | None:
        return self._by

    def trigger(self, threat_type: str, triggered_by: str = "manual") -> None:
        self._active = True
        self._threat = threat_type
        self._by = triggered_by
        self.trigger_calls.append((threat_type, triggered_by))

    def cancel(self) -> None:
        self._active = False
        self._threat = None
        self._by = None
        self.cancel_calls += 1


def _alert(alert_id: str, threat: str = "flood", severity: str = "severe",
           lat: float = 48.85, lon: float = 2.35,
           expires: datetime | None = None) -> GouvAlert:
    return GouvAlert(
        alert_id=alert_id,
        threat_type=threat,
        severity=severity,
        title="t",
        message="m",
        source="fake",
        zone_lat=lat,
        zone_lon=lon,
        starts_at=datetime.now(timezone.utc),
        expires_at=expires,
    )


def _make_hass_with_home(lat=48.85, lon=2.35):
    hass = MagicMock()
    zone_state = MagicMock()
    zone_state.attributes = {"latitude": lat, "longitude": lon, "radius": 100}
    hass.states.get = MagicMock(return_value=zone_state)
    return hass


@pytest.mark.asyncio
async def test_poll_triggers_alert_when_matching():
    provider = _FakeProvider([_alert("a1", threat="flood", severity="severe")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert coord.trigger_calls == [("flood", "provider:fake")]
    assert "a1" in mgr.known_alert_ids


@pytest.mark.asyncio
async def test_poll_ignores_below_min_severity():
    provider = _FakeProvider([_alert("a1", severity="moderate")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert coord.trigger_calls == []
    assert mgr.known_alert_ids == set()


@pytest.mark.asyncio
async def test_poll_filters_by_distance():
    # Alert at (46, 2) — ~300km from Paris
    provider = _FakeProvider([_alert("a1", lat=46.0, lon=2.0)])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(48.85, 2.35),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert coord.trigger_calls == []


@pytest.mark.asyncio
async def test_poll_dedupes_existing_alert_id():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()
    await mgr.async_poll_once()

    assert len(coord.trigger_calls) == 1  # not re-triggered


@pytest.mark.asyncio
async def test_auto_cancel_when_alert_disappears():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )
    await mgr.async_poll_once()
    assert coord.trigger_calls

    provider._alerts = []  # source now returns nothing
    await mgr.async_poll_once()

    assert coord.cancel_calls == 1
    assert "a1" not in mgr.known_alert_ids


@pytest.mark.asyncio
async def test_auto_cancel_disabled_keeps_alert_active():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=False,
        min_severity="severe",
    )
    await mgr.async_poll_once()
    provider._alerts = []
    await mgr.async_poll_once()

    assert coord.cancel_calls == 0


@pytest.mark.asyncio
async def test_auto_cancel_only_cancels_own_trigger():
    """If the active alert was triggered manually, manager must not cancel it."""
    provider = _FakeProvider([])
    coord = _FakeCoordinator()
    coord.trigger("storm", triggered_by="manual")
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert coord.cancel_calls == 0


@pytest.mark.asyncio
async def test_does_not_trigger_when_alert_already_active():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    coord.trigger("attack", triggered_by="manual")  # something else is active
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    # coord.trigger_calls = [("attack","manual")] from setup; no new call
    assert coord.trigger_calls == [("attack", "manual")]


@pytest.mark.asyncio
async def test_trigger_callback_called_on_trigger():
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    calls: list[int] = []
    mgr = AlertProviderManager(
        hass=_make_hass_with_home(),
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: calls.append(1),
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert calls == [1]


@pytest.mark.asyncio
async def test_no_zone_home_skips_poll():
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    provider = _FakeProvider([_alert("a1")])
    coord = _FakeCoordinator()
    mgr = AlertProviderManager(
        hass=hass,
        providers=[provider],
        alert_coordinator=coord,
        trigger_callback=lambda: None,
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    assert provider.calls == 0
    assert coord.trigger_calls == []
