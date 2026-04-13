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
