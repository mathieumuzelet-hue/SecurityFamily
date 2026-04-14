"""DataUpdateCoordinator for Shelter Finder."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cache import ShelterCache
from .overpass import OverpassClient
from .shelter_logic import compute_adaptive_radii, merge_shelters_and_pois

_LOGGER = logging.getLogger(__name__)


class ShelterUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator that fetches shelter data from Overpass and merges with POIs."""

    def __init__(
        self,
        hass: HomeAssistant,
        cache: ShelterCache,
        overpass_client: OverpassClient,
        persons: list[str],
        search_radius: int,
        adaptive_radius: bool = True,
        adaptive_radius_max: int = 15000,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="shelter_finder",
            update_interval=timedelta(hours=24),
        )
        self.cache = cache
        self.overpass_client = overpass_client
        self.persons = persons
        self.search_radius = search_radius
        self.adaptive_radius = adaptive_radius
        self.adaptive_radius_max = adaptive_radius_max

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch shelter data from cache or Overpass."""
        try:
            cache_valid = await self.hass.async_add_executor_job(self.cache.is_valid)
            if cache_valid:
                shelters = await self.hass.async_add_executor_job(self.cache.load)
                _LOGGER.debug("Using cached shelter data (%d shelters)", len(shelters))
            else:
                shelters = await self._fetch_from_overpass()

            pois = await self.hass.async_add_executor_job(self.cache.load_pois)
            return merge_shelters_and_pois(shelters, pois)
        except Exception as err:
            raise UpdateFailed(f"Failed to update shelter data: {err}") from err

    def _collect_person_positions(self) -> list[tuple[str, float, float]]:
        """Return (person_id, lat, lon) for each person that has a known location."""
        positions: list[tuple[str, float, float]] = []
        for person_id in self.persons:
            state = self.hass.states.get(person_id)
            if state is None:
                _LOGGER.debug("Person %s has no state, skipping", person_id)
                continue
            lat = state.attributes.get("latitude")
            lon = state.attributes.get("longitude")
            if lat is None or lon is None:
                _LOGGER.debug("Person %s has no location, skipping", person_id)
                continue
            positions.append((person_id, float(lat), float(lon)))
        return positions

    async def _fetch_around(
        self, lat: float, lon: float,
    ) -> list[dict[str, Any]]:
        """Run an Overpass query at (lat, lon) with adaptive widening."""
        shelters = await self.overpass_client.fetch_shelters(lat, lon, self.search_radius)

        if self.adaptive_radius:
            radii = compute_adaptive_radii(
                self.search_radius, self.adaptive_radius_max, len(shelters),
            )
            for radius in radii:
                extra = await self.overpass_client.fetch_shelters(lat, lon, radius)
                shelters.extend(extra)
                if len(shelters) >= 3:
                    break

        return shelters

    @staticmethod
    def _dedup_key(shelter: dict[str, Any]) -> Any:
        """Stable key to dedupe shelters across per-person queries."""
        osm_id = shelter.get("id") or shelter.get("osm_id")
        if osm_id:
            return ("id", osm_id)
        lat = shelter.get("latitude")
        lon = shelter.get("longitude")
        return ("coord", round(float(lat), 5), round(float(lon), 5))

    async def _fetch_from_overpass(self) -> list[dict[str, Any]]:
        """Fetch shelters around each person's current location with adaptive radius.

        Runs one Overpass query per person that has a known position, merges
        and deduplicates results. Falls back to ``zone.home`` only if no
        person has a location. On Overpass failure, returns the stale cache
        once (not per-person).
        """
        positions = self._collect_person_positions()

        if not positions:
            home = self.hass.states.get("zone.home")
            if home is None:
                raise UpdateFailed(
                    "No person has a known location and zone.home is missing",
                )
            home_lat = home.attributes.get("latitude")
            home_lon = home.attributes.get("longitude")
            if home_lat is None or home_lon is None:
                raise UpdateFailed(
                    "No person has a known location and zone.home has no coordinates",
                )
            _LOGGER.debug(
                "No person location available, falling back to zone.home",
            )
            positions = [("zone.home", float(home_lat), float(home_lon))]

        try:
            merged: dict[Any, dict[str, Any]] = {}
            for person_id, lat, lon in positions:
                per_person = await self._fetch_around(lat, lon)
                _LOGGER.debug(
                    "Overpass returned %d shelters around %s",
                    len(per_person), person_id,
                )
                for shelter in per_person:
                    merged.setdefault(self._dedup_key(shelter), shelter)

            shelters = list(merged.values())
            await self.hass.async_add_executor_job(self.cache.save, shelters)
            return shelters

        except Exception as err:
            _LOGGER.warning("Overpass fetch failed: %s, trying stale cache", err)
            stale = await self.hass.async_add_executor_job(self.cache.load_stale)
            if stale:
                return stale
            raise

    async def async_force_refresh(self) -> None:
        """Invalidate cache and force a fresh Overpass fetch."""
        self.cache._ttl_seconds = 0
        await self.async_refresh()
