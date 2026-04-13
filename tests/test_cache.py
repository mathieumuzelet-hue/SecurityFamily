"""Tests for Shelter Finder cache module."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from custom_components.shelter_finder.cache import ShelterCache


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path

@pytest.fixture
def cache(cache_dir: Path) -> ShelterCache:
    return ShelterCache(cache_dir, ttl_hours=1)


def test_save_and_load(cache: ShelterCache) -> None:
    shelters = [
        {"id": "1", "name": "Abri A", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker"},
        {"id": "2", "name": "Abri B", "latitude": 48.86, "longitude": 2.36, "shelter_type": "subway"},
    ]
    cache.save(shelters)
    loaded = cache.load()
    assert loaded == shelters

def test_load_empty_cache(cache: ShelterCache) -> None:
    assert cache.load() == []

def test_cache_expired(cache_dir: Path) -> None:
    cache = ShelterCache(cache_dir, ttl_hours=0)
    shelters = [{"id": "1", "name": "Test", "latitude": 0, "longitude": 0, "shelter_type": "shelter"}]
    cache.save(shelters)
    cache_file = cache_dir / "shelter_finder_cache.json"
    old_time = time.time() - 7200
    import os
    os.utime(cache_file, (old_time, old_time))
    assert cache.load() == []

def test_cache_not_expired(cache: ShelterCache) -> None:
    shelters = [{"id": "1", "name": "Test", "latitude": 0, "longitude": 0, "shelter_type": "shelter"}]
    cache.save(shelters)
    loaded = cache.load()
    assert loaded == shelters

def test_is_valid_property(cache: ShelterCache) -> None:
    assert cache.is_valid is False
    cache.save([{"id": "1", "name": "Test", "latitude": 0, "longitude": 0, "shelter_type": "shelter"}])
    assert cache.is_valid is True

def test_corrupted_cache_returns_empty(cache: ShelterCache, cache_dir: Path) -> None:
    cache_file = cache_dir / "shelter_finder_cache.json"
    cache_file.write_text("not valid json{{{")
    assert cache.load() == []

def test_save_pois_and_load(cache: ShelterCache) -> None:
    pois = [{"id": "poi1", "name": "Cave maison", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker"}]
    cache.save_pois(pois)
    loaded = cache.load_pois()
    assert loaded == pois

def test_load_pois_empty(cache: ShelterCache) -> None:
    assert cache.load_pois() == []

def test_load_stale(cache_dir: Path) -> None:
    cache = ShelterCache(cache_dir, ttl_hours=0)
    shelters = [{"id": "1", "name": "Stale", "latitude": 0, "longitude": 0, "shelter_type": "shelter"}]
    cache.save(shelters)
    cache_file = cache_dir / "shelter_finder_cache.json"
    old_time = time.time() - 7200
    import os
    os.utime(cache_file, (old_time, old_time))
    # load() should return empty (expired)
    assert cache.load() == []
    # load_stale() should return data regardless of TTL
    assert cache.load_stale() == shelters
