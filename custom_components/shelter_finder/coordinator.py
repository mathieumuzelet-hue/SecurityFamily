"""DataUpdateCoordinator for Shelter Finder."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from .cache import ShelterCache
from .const import DOMAIN
from .overpass import OverpassClient
from .shelter_logic import compute_adaptive_radii, merge_shelters_and_pois

_LOGGER = logging.getLogger(__name__)


class ShelterUpdateCoordinator:
    """Coordinator that fetches shelter data from Overpass and merges with POIs.

    Note: This is a simplified coordinator that does NOT inherit from
    homeassistant.helpers.update_coordinator.DataUpdateCoordinator to keep
    tests runnable without the full HA test infrastructure. The __init__.py
    integration setup (Task 13) wraps this with the proper HA coordinator pattern.
    """

    def __init__(
        self,
        hass: Any,
        cache: ShelterCache,
        overpass_client: OverpassClient,
        persons: list[str],
        search_radius: int,
        adaptive_radius: bool = True,
        adaptive_radius_max: int = 15000,
    ) -> None:
        self.hass = hass
        self.cache = cache
        self.overpass_client = overpass_client
        self.persons = persons
        self.search_radius = search_radius
        self.adaptive_radius = adaptive_radius
        self.adaptive_radius_max = adaptive_radius_max
        self.data: list[dict[str, Any]] = []
        self.update_interval = timedelta(hours=24)

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch shelter data from cache or Overpass."""
        if self.cache.is_valid:
            shelters = self.cache.load()
            _LOGGER.debug("Using cached shelter data (%d shelters)", len(shelters))
        else:
            shelters = await self._fetch_from_overpass()

        pois = self.cache.load_pois()
        merged = merge_shelters_and_pois(shelters, pois)
        self.data = merged
        return merged

    async def _fetch_from_overpass(self) -> list[dict[str, Any]]:
        """Fetch shelters from Overpass with adaptive radius and fallback."""
        home = self.hass.states.get("zone.home")
        if home is None:
            raise RuntimeError("zone.home not found")

        lat = home.attributes.get("latitude", 0)
        lon = home.attributes.get("longitude", 0)

        try:
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

            self.cache.save(shelters)
            return shelters

        except Exception as err:
            _LOGGER.warning("Overpass fetch failed: %s, trying stale cache", err)
            stale = self.cache.load_stale()
            if stale:
                return stale
            raise

    async def async_request_refresh(self) -> None:
        """Force a data refresh."""
        self.cache._ttl_seconds = 0  # Force cache invalidation
        await self._async_update_data()
