"""Local file cache for shelter data."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

CACHE_FILENAME = "shelter_finder_cache.json"
POI_FILENAME = "shelter_finder_pois.json"


class ShelterCache:
    """File-based JSON cache with TTL for shelter data."""

    def __init__(self, storage_dir: Path, ttl_hours: int = 24) -> None:
        self._storage_dir = storage_dir
        self._ttl_seconds = ttl_hours * 3600
        self._cache_file = storage_dir / CACHE_FILENAME
        self._poi_file = storage_dir / POI_FILENAME

    @property
    def is_valid(self) -> bool:
        if not self._cache_file.exists():
            return False
        age = time.time() - self._cache_file.stat().st_mtime
        return age < self._ttl_seconds

    def save(self, shelters: list[dict[str, Any]]) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file.write_text(json.dumps(shelters, ensure_ascii=False), encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        if not self.is_valid:
            return []
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            _LOGGER.warning("Cache file corrupted, returning empty")
            return []

    def load_stale(self) -> list[dict[str, Any]]:
        """Load cache data regardless of TTL."""
        if not self._cache_file.exists():
            return []
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def save_pois(self, pois: list[dict[str, Any]]) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._poi_file.write_text(json.dumps(pois, ensure_ascii=False), encoding="utf-8")

    def load_pois(self) -> list[dict[str, Any]]:
        if not self._poi_file.exists():
            return []
        try:
            data = json.loads(self._poi_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            _LOGGER.warning("POI file corrupted, returning empty")
            return []
