"""Routing calculations for Shelter Finder."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import TRAVEL_SPEEDS

_LOGGER = logging.getLogger(__name__)


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
        warn_throttle_s: float = 600.0,
    ) -> None:
        self.session = session
        self.enabled = enabled
        self.url = url.rstrip("/")
        self.transport_mode = transport_mode
        self.timeout_s = timeout_s
        self.cache_ttl_s = cache_ttl_s
        self.cache_max = cache_max
        self.warn_throttle_s = warn_throttle_s
        self._last_warn_at: float = 0.0

    async def async_get_route(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> RouteResult:
        if not self.enabled or self.session is None:
            return self._haversine_result(lat1, lon1, lat2, lon2)

        key = self._cache_key(lat1, lon1, lat2, lon2)
        now = time.monotonic()
        cached = self._cache_get(key, now=now)
        if cached is not None:
            return cached

        url = (
            f"{self.url}/route/v1/{self.transport_mode}/"
            f"{lon1},{lat1};{lon2},{lat2}?overview=false"
        )
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s)
            async with self.session.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                data = await resp.json()
            routes = data.get("routes") or []
            if not routes:
                raise ValueError(f"OSRM returned no routes: {data.get('code')}")
            route = routes[0]
            result = RouteResult(
                distance_m=float(route["distance"]),
                eta_seconds=float(route["duration"]),
                source="osrm",
            )
            self._cache_put(key, result, now=now)
            return result
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as err:
            self._maybe_log_warning(err)
            return self._haversine_result(lat1, lon1, lat2, lon2)

    def _should_log_warning(self, now: float) -> bool:
        if now - self._last_warn_at >= self.warn_throttle_s:
            self._last_warn_at = now
            return True
        return False

    def _maybe_log_warning(self, err: Exception) -> None:
        if self._should_log_warning(time.monotonic()):
            _LOGGER.warning("OSRM call failed, falling back to haversine: %s", err)

    def _haversine_result(
        self, lat1: float, lon1: float, lat2: float, lon2: float,
    ) -> RouteResult:
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        mode_key = "driving" if self.transport_mode == "driving" else "walking"
        speed = TRAVEL_SPEEDS.get(mode_key, TRAVEL_SPEEDS["walking"])
        return RouteResult(distance_m=distance, eta_seconds=distance / speed, source="haversine")

    # --- cache internals ---

    def _cache(self) -> "OrderedDict[tuple, tuple[float, RouteResult]]":
        if not hasattr(self, "_cache_store"):
            self._cache_store: OrderedDict[tuple, tuple[float, RouteResult]] = OrderedDict()
        return self._cache_store

    @staticmethod
    def _cache_key(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple:
        return (round(lat1, 4), round(lon1, 4), round(lat2, 4), round(lon2, 4))

    def _cache_get(self, key: tuple, now: float) -> RouteResult | None:
        cache = self._cache()
        entry = cache.get(key)
        if entry is None:
            return None
        inserted_at, result = entry
        if now - inserted_at > self.cache_ttl_s:
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        return result

    def _cache_put(self, key: tuple, result: RouteResult, now: float) -> None:
        cache = self._cache()
        cache[key] = (now, result)
        cache.move_to_end(key)
        while len(cache) > self.cache_max:
            cache.popitem(last=False)

    async def async_get_routes_batch(
        self,
        person_lat: float,
        person_lon: float,
        candidates: list[dict[str, Any]],
        top_n: int = 10,
    ) -> dict[str, RouteResult]:
        """Return {candidate_id: RouteResult}.

        Prefilters candidates by haversine and only queries OSRM for the top N
        nearest. Remaining candidates receive a haversine RouteResult directly.
        An `id` key must be present on each candidate.
        """
        # Compute haversine for all
        scored = []
        for c in candidates:
            d = haversine_distance(person_lat, person_lon, c["latitude"], c["longitude"])
            scored.append((d, c))
        scored.sort(key=lambda x: x[0])

        results: dict[str, RouteResult] = {}
        top = scored[:top_n]
        rest = scored[top_n:]

        # OSRM for top N (parallel)
        tasks = [
            self.async_get_route(person_lat, person_lon, c["latitude"], c["longitude"])
            for _, c in top
        ]
        if tasks:
            top_results = await asyncio.gather(*tasks)
            for (_, c), r in zip(top, top_results):
                results[c["id"]] = r

        # Haversine for the rest
        for d, c in rest:
            results[c["id"]] = self._haversine_result(
                person_lat, person_lon, c["latitude"], c["longitude"]
            )

        return results
