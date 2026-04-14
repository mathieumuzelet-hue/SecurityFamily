"""Shelter scoring, ranking, and adaptive radius logic."""

from __future__ import annotations

import math
from typing import Any

from .const import ADAPTIVE_RADIUS_MIN_RESULTS, THREAT_SHELTER_SCORES


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def score_shelter(shelter: dict[str, Any], threat_type: str, distance_m: float) -> float:
    scores = THREAT_SHELTER_SCORES.get(threat_type, {})
    type_score = scores.get(shelter.get("shelter_type", ""), 0)
    distance_bonus = max(0.0, 10.0 * (1.0 - distance_m / 15000.0))
    return type_score * 10.0 + distance_bonus


def rank_shelters(
    shelters: list[dict[str, Any]],
    threat_type: str,
    person_lat: float,
    person_lon: float,
    extra_distances: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    scored = []
    for shelter in shelters:
        shelter_id = shelter.get("id")
        if extra_distances is not None and shelter_id in extra_distances:
            distance = extra_distances[shelter_id]
        else:
            distance = _haversine_distance(person_lat, person_lon, shelter["latitude"], shelter["longitude"])
        s = score_shelter(shelter, threat_type, distance)
        scored.append({**shelter, "distance_m": round(distance), "score": s})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def compute_adaptive_radii(base_radius: int, max_radius: int, found_count: int, min_results: int = ADAPTIVE_RADIUS_MIN_RESULTS) -> list[int]:
    if found_count >= min_results:
        return []
    expanded = []
    r1 = int(base_radius * 2.5)
    r2 = int(base_radius * 5)
    if r1 <= max_radius:
        expanded.append(r1)
    if r2 <= max_radius and r2 != r1:
        expanded.append(r2)
    return expanded


def deduplicate_shelters(shelters: list[dict[str, Any]], threshold_m: float = 50.0) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for shelter in shelters:
        is_dup = False
        for existing in result:
            dist = _haversine_distance(shelter["latitude"], shelter["longitude"], existing["latitude"], existing["longitude"])
            if dist < threshold_m:
                is_dup = True
                break
        if not is_dup:
            result.append(shelter)
    return result


def merge_shelters_and_pois(osm_shelters: list[dict[str, Any]], pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined = list(pois) + list(osm_shelters)
    return deduplicate_shelters(combined)
