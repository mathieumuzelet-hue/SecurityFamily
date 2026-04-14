"""Orchestrator for FR-Alert / SAIP providers."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from ._geo import haversine_km
from .alert_coordinator import AlertCoordinator
from .alert_providers.base import AlertProvider, GouvAlert, meets_min_severity

_LOGGER = logging.getLogger(__name__)

_PROVIDER_TRIGGER_PREFIX = "provider:"


class AlertProviderManager:
    """Polls providers, filters alerts, drives AlertCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        providers: list[AlertProvider],
        alert_coordinator: AlertCoordinator,
        trigger_callback: Callable[[], None],
        polling_interval: int,
        radius_km: float,
        auto_cancel: bool,
        min_severity: str,
        zone_entity_id: str = "zone.home",
    ) -> None:
        self._hass = hass
        self._providers = providers
        self._coord = alert_coordinator
        self._trigger_callback = trigger_callback
        self._polling_interval = polling_interval
        self._radius_km = radius_km
        self._auto_cancel = auto_cancel
        self._min_severity = min_severity
        self._zone_entity_id = zone_entity_id
        self._known_alert_ids: set[str] = set()
        self._active_alert_id: str | None = None
        self._unsub: Callable[[], None] | None = None
        self._in_flight: asyncio.Task | None = None

    @property
    def known_alert_ids(self) -> set[str]:
        return set(self._known_alert_ids)

    async def async_start(self) -> None:
        """Start periodic polling."""
        if self._unsub is not None:
            return
        # Fire once immediately so the first poll does not wait a full interval
        await self.async_poll_once()
        self._unsub = async_track_time_interval(
            self._hass,
            self._scheduled_tick,
            timedelta(seconds=self._polling_interval),
        )
        _LOGGER.info(
            "AlertProviderManager started: %d provider(s), interval=%ss, radius=%skm",
            len(self._providers), self._polling_interval, self._radius_km,
        )

    async def async_stop(self) -> None:
        """Stop periodic polling."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._in_flight is not None and not self._in_flight.done():
            self._in_flight.cancel()
            try:
                await self._in_flight
            except asyncio.CancelledError:
                pass
            except Exception as err:  # pragma: no cover
                _LOGGER.debug(
                    "In-flight poll raised during async_stop: %s", err, exc_info=True,
                )
        self._in_flight = None

    async def _scheduled_tick(self, _now) -> None:
        if self._in_flight is not None and not self._in_flight.done():
            _LOGGER.debug("Previous poll still running, skipping tick")
            return
        self._in_flight = self._hass.async_create_task(self.async_poll_once())

    async def async_poll_once(self) -> None:
        """Run one full poll cycle across all providers."""
        home = self._hass.states.get(self._zone_entity_id)
        if home is None:
            _LOGGER.debug("%s not available, skipping poll", self._zone_entity_id)
            return
        home_lat = home.attributes.get("latitude")
        home_lon = home.attributes.get("longitude")
        if home_lat is None or home_lon is None:
            _LOGGER.debug("zone.home has no coordinates, skipping poll")
            return

        # Fetch from all providers concurrently; a provider error yields [].
        results = await asyncio.gather(
            *[p.async_fetch_alerts(home_lat, home_lon, self._radius_km) for p in self._providers],
            return_exceptions=True,
        )
        collected: list[GouvAlert] = []
        for provider, res in zip(self._providers, results):
            if isinstance(res, Exception):
                _LOGGER.warning("Provider %s errored: %s", provider.source_name, res)
                continue
            collected.extend(res)

        # Filter by severity and distance.
        qualifying: list[GouvAlert] = []
        for alert in collected:
            if not meets_min_severity(alert.severity, self._min_severity):
                continue
            dist = haversine_km(home_lat, home_lon, alert.zone_lat, alert.zone_lon)
            if dist > self._radius_km:
                continue
            qualifying.append(alert)

        qualifying_ids = {a.alert_id for a in qualifying}

        # Trigger on the first new qualifying alert if nothing active.
        for alert in qualifying:
            if alert.alert_id in self._known_alert_ids:
                continue
            self._known_alert_ids.add(alert.alert_id)
            if self._coord.is_active:
                _LOGGER.debug("Alert already active, not re-triggering for %s", alert.alert_id)
                continue
            self._coord.trigger(
                alert.threat_type,
                triggered_by=f"{_PROVIDER_TRIGGER_PREFIX}{alert.source}",
            )
            self._active_alert_id = alert.alert_id
            _LOGGER.info(
                "FR-Alert triggered %s (%s, %s) from %s",
                alert.threat_type, alert.severity, alert.alert_id, alert.source,
            )
            try:
                self._trigger_callback()
            except Exception:  # pragma: no cover
                _LOGGER.exception("trigger_callback raised")
            break

        # Drop IDs that are gone from the source so they can re-trigger later.
        self._known_alert_ids &= qualifying_ids | ({self._active_alert_id} if self._active_alert_id else set())

        # Auto-cancel only if we own the active alert and it disappeared.
        if (
            self._auto_cancel
            and self._coord.is_active
            and self._active_alert_id is not None
            and self._active_alert_id not in qualifying_ids
            and (self._coord.triggered_by or "").startswith(_PROVIDER_TRIGGER_PREFIX)
        ):
            _LOGGER.info("FR-Alert auto-cancelling %s (no longer in source)", self._active_alert_id)
            self._coord.cancel()
            self._known_alert_ids.discard(self._active_alert_id)
            self._active_alert_id = None
