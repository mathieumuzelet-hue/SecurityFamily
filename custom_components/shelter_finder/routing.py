"""Routing calculations for Shelter Finder."""

from __future__ import annotations

import math

from .const import TRAVEL_SPEEDS


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_eta_minutes(distance_m: float, travel_mode: str) -> float:
    if distance_m <= 0:
        return 0.0
    speed_ms = TRAVEL_SPEEDS.get(travel_mode, TRAVEL_SPEEDS["walking"])
    return round(distance_m / speed_ms / 60, 1)


from dataclasses import dataclass
from typing import Any


@dataclass
class RouteResult:
    distance_m: float
    eta_seconds: float
    source: str  # "osrm" or "haversine"


class RoutingService:
    """Wraps OSRM API with LRU+TTL cache and haversine fallback."""

    def __init__(
        self,
        session: Any,
        enabled: bool = False,
        url: str = "https://router.project-osrm.org",
        transport_mode: str = "foot",
        timeout_s: float = 5.0,
        cache_ttl_s: float = 300.0,
        cache_max: int = 500,
    ) -> None:
        self.session = session
        self.enabled = enabled
        self.url = url.rstrip("/")
        self.transport_mode = transport_mode
        self.timeout_s = timeout_s
        self.cache_ttl_s = cache_ttl_s
        self.cache_max = cache_max
