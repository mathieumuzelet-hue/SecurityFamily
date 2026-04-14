"""Alert coordinator for Shelter Finder."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .const import THREAT_TYPES
from .routing import RoutingService, calculate_eta_minutes
from .shelter_logic import rank_shelters

_LOGGER = logging.getLogger(__name__)


class AlertCoordinator:
    def __init__(
        self,
        hass: Any,
        shelter_coordinator: Any,
        persons: list[str],
        travel_mode: str = "walking",
        re_notification_interval: int = 5,
        max_re_notifications: int = 3,
        routing_service: "RoutingService | None" = None,
    ) -> None:
        self.hass = hass
        self.shelter_coordinator = shelter_coordinator
        self.persons = persons
        self.travel_mode = travel_mode
        self.re_notification_interval = re_notification_interval
        self.max_re_notifications = max_re_notifications
        self.routing_service = routing_service
        self._is_active = False
        self._threat_type: str | None = None
        self._triggered_by: str | None = None
        self._triggered_at: datetime | None = None
        self._persons_safe: list[str] = []
        self._notification_counts: dict[str, int] = {}
        self._is_drill: bool = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def threat_type(self) -> str | None:
        return self._threat_type

    @property
    def triggered_by(self) -> str | None:
        return self._triggered_by

    @property
    def triggered_at(self) -> datetime | None:
        return self._triggered_at

    @property
    def is_drill(self) -> bool:
        return self._is_drill

    @property
    def persons_safe(self) -> list[str]:
        return list(self._persons_safe)

    @property
    def all_safe(self) -> bool:
        if not self._is_active:
            return False
        return all(p in self._persons_safe for p in self.persons)

    def trigger(self, threat_type: str, triggered_by: str = "manual", drill: bool = False) -> None:
        if threat_type not in THREAT_TYPES:
            raise ValueError(f"Unknown threat type: {threat_type}")
        self._is_active = True
        self._threat_type = threat_type
        self._triggered_by = triggered_by
        self._triggered_at = datetime.now(timezone.utc)
        self._persons_safe = []
        self._notification_counts = {p: 0 for p in self.persons}
        self._is_drill = drill

    def cancel(self) -> None:
        self._is_active = False
        self._threat_type = None
        self._triggered_by = None
        self._triggered_at = None
        self._persons_safe = []
        self._notification_counts = {}
        self._is_drill = False

    def confirm_safe(self, person_entity_id: str) -> None:
        if not self._is_active:
            return
        if person_entity_id not in self._persons_safe:
            self._persons_safe.append(person_entity_id)

    async def get_best_shelter(self, person_entity_id: str) -> dict[str, Any] | None:
        if not self._is_active or self._threat_type is None:
            return None
        state = self.hass.states.get(person_entity_id)
        if state is None:
            return None
        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is None or lon is None:
            return None
        shelters = self.shelter_coordinator.data or []
        if not shelters:
            return None

        # Ensure every shelter has an id (OSM ones usually do; synthesize otherwise)
        normalized = []
        for s in shelters:
            if "id" not in s:
                s = {**s, "id": f"{s.get('latitude')}_{s.get('longitude')}"}
            normalized.append(s)

        route_source = "haversine"
        extra_distances: dict[str, float] = {}
        eta_lookup: dict[str, float] = {}
        if self.routing_service is not None:
            routes = await self.routing_service.async_get_routes_batch(
                lat, lon, normalized, top_n=10,
            )
            for sid, r in routes.items():
                extra_distances[sid] = r.distance_m
                eta_lookup[sid] = r.eta_seconds
            if routes and any(r.source == "osrm" for r in routes.values()):
                route_source = "osrm"

        ranked = rank_shelters(
            normalized, self._threat_type, lat, lon,
            extra_distances=extra_distances or None,
        )
        if not ranked:
            return None
        best = ranked[0]
        best_id = best["id"]
        eta_seconds = eta_lookup.get(best_id)
        if eta_seconds is not None:
            best["eta_minutes"] = round(eta_seconds / 60.0, 1)
        else:
            best["eta_minutes"] = calculate_eta_minutes(best["distance_m"], self.travel_mode)
        best["route_source"] = route_source
        return best

    def should_re_notify(self, person_entity_id: str) -> bool:
        if not self._is_active:
            return False
        if person_entity_id in self._persons_safe:
            return False
        count = self._notification_counts.get(person_entity_id, 0)
        return count < self.max_re_notifications

    def record_notification(self, person_entity_id: str) -> None:
        self._notification_counts[person_entity_id] = self._notification_counts.get(person_entity_id, 0) + 1
