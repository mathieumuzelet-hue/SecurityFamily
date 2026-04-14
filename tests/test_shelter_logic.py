"""Tests for Shelter Finder shelter logic."""

from __future__ import annotations

import pytest

from custom_components.shelter_finder.shelter_logic import (
    compute_adaptive_radii,
    deduplicate_shelters,
    merge_shelters_and_pois,
    rank_shelters,
    score_shelter,
)


def test_score_shelter_storm_bunker() -> None:
    shelter = {"shelter_type": "bunker", "latitude": 48.85, "longitude": 2.35}
    score = score_shelter(shelter, "storm", distance_m=500)
    assert score > 0

def test_score_shelter_earthquake_open_space() -> None:
    open_space = {"shelter_type": "open_space", "latitude": 48.85, "longitude": 2.35}
    bunker = {"shelter_type": "bunker", "latitude": 48.85, "longitude": 2.35}
    score_open = score_shelter(open_space, "earthquake", distance_m=500)
    score_bunker = score_shelter(bunker, "earthquake", distance_m=500)
    assert score_open > score_bunker

def test_score_shelter_closer_is_better() -> None:
    shelter = {"shelter_type": "bunker", "latitude": 48.85, "longitude": 2.35}
    score_close = score_shelter(shelter, "storm", distance_m=200)
    score_far = score_shelter(shelter, "storm", distance_m=5000)
    assert score_close > score_far

def test_score_shelter_unknown_type() -> None:
    shelter = {"shelter_type": "unknown_thing", "latitude": 48.85, "longitude": 2.35}
    score = score_shelter(shelter, "storm", distance_m=500)
    assert score >= 0

def test_rank_shelters() -> None:
    shelters = [
        {"name": "Far bunker", "shelter_type": "bunker", "latitude": 48.85, "longitude": 2.35},
        {"name": "Close subway", "shelter_type": "subway", "latitude": 48.856, "longitude": 2.352},
    ]
    ranked = rank_shelters(shelters, "storm", person_lat=48.856, person_lon=2.352)
    assert ranked[0]["name"] == "Close subway"

def test_rank_shelters_empty() -> None:
    assert rank_shelters([], "storm", person_lat=48.85, person_lon=2.35) == []

def test_adaptive_radii_enough_results() -> None:
    radii = compute_adaptive_radii(2000, 15000, found_count=5, min_results=3)
    assert radii == []

def test_adaptive_radii_not_enough() -> None:
    radii = compute_adaptive_radii(2000, 15000, found_count=1, min_results=3)
    assert len(radii) > 0
    assert radii[0] == 5000
    assert radii[1] == 10000

def test_adaptive_radii_capped() -> None:
    radii = compute_adaptive_radii(5000, 15000, found_count=0, min_results=3)
    assert all(r <= 15000 for r in radii)

def test_deduplicate_shelters_nearby() -> None:
    shelters = [
        {"osm_id": "node/1", "name": "A", "latitude": 48.85000, "longitude": 2.35000, "source": "manual"},
        {"osm_id": "node/2", "name": "B", "latitude": 48.85001, "longitude": 2.35001, "source": "osm"},
    ]
    result = deduplicate_shelters(shelters, threshold_m=50)
    assert len(result) == 1
    assert result[0]["name"] == "A"

def test_deduplicate_shelters_far_apart() -> None:
    shelters = [
        {"osm_id": "node/1", "name": "A", "latitude": 48.85, "longitude": 2.35, "source": "osm"},
        {"osm_id": "node/2", "name": "B", "latitude": 48.86, "longitude": 2.36, "source": "osm"},
    ]
    result = deduplicate_shelters(shelters, threshold_m=50)
    assert len(result) == 2

def test_merge_pois_first() -> None:
    osm = [{"osm_id": "node/1", "name": "OSM Shelter", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter", "source": "osm"}]
    pois = [{"id": "poi1", "name": "Ma Cave", "latitude": 48.86, "longitude": 2.36, "shelter_type": "bunker", "source": "manual"}]
    merged = merge_shelters_and_pois(osm, pois)
    assert len(merged) == 2
    assert merged[0]["source"] == "manual"

def test_merge_deduplicates() -> None:
    osm = [{"osm_id": "node/1", "name": "OSM Shelter", "latitude": 48.85000, "longitude": 2.35000, "shelter_type": "shelter", "source": "osm"}]
    pois = [{"id": "poi1", "name": "Ma Cave", "latitude": 48.85001, "longitude": 2.35001, "shelter_type": "bunker", "source": "manual"}]
    merged = merge_shelters_and_pois(osm, pois)
    assert len(merged) == 1
    assert merged[0]["name"] == "Ma Cave"


def test_rank_shelters_uses_extra_distances_when_provided() -> None:
    from custom_components.shelter_finder.shelter_logic import rank_shelters

    shelters = [
        {"id": "s1", "latitude": 48.854, "longitude": 2.350, "shelter_type": "subway"},
        {"id": "s2", "latitude": 48.858, "longitude": 2.340, "shelter_type": "bunker"},
    ]
    # Override: pretend OSRM tells us s2 is much closer than s1
    overrides = {"s1": 5000.0, "s2": 100.0}
    ranked = rank_shelters(
        shelters, "attack", person_lat=48.8530, person_lon=2.3499,
        extra_distances=overrides,
    )
    # s2 should now win with its short OSRM distance
    assert ranked[0]["id"] == "s2"
    assert ranked[0]["distance_m"] == 100
    # s1 got the overridden long distance
    s1 = next(s for s in ranked if s["id"] == "s1")
    assert s1["distance_m"] == 5000
