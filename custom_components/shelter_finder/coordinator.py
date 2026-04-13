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

    async def _fetch_from_overpass(self) -> list[dict[str, Any]]:
        """Fetch shelters from Overpass with adaptive radius and fallback."""
        home = self.hass.states.get("zone.home")
        if home is None:
            raise UpdateFailed("zone.home not found")

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
