"""Shared geographic helpers.

Kept deliberately small and dependency-free so it can be imported from
provider modules without pulling in HA / aiohttp.
"""

from __future__ import annotations

from .routing import haversine_distance


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in kilometers."""
    return haversine_distance(lat1, lon1, lat2, lon2) / 1000.0
