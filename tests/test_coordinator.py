"""Tests for ShelterUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.shelter_finder.coordinator import ShelterUpdateCoordinator


@pytest.fixture
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.is_valid = MagicMock(return_value=False)
    cache.load.return_value = []
    cache.load_pois.return_value = []
    cache.load_stale.return_value = []
    cache.save = MagicMock()
    return cache

@pytest.fixture
def mock_overpass_client() -> AsyncMock:
    client = AsyncMock()
    client.fetch_shelters = AsyncMock(return_value=[
        {"osm_id": "node/1", "name": "Abri Test", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter", "source": "osm"},
    ])
    return client

@pytest.fixture
def mock_hass() -> MagicMock:
    hass = MagicMock()
    home_state = MagicMock()
    home_state.attributes = {"latitude": 48.85, "longitude": 2.35}
    hass.states.get.return_value = home_state
    # Mock the event loop
    import asyncio
    hass.loop = asyncio.new_event_loop()
    return hass

@pytest.fixture
def coordinator(mock_hass, mock_cache, mock_overpass_client) -> ShelterUpdateCoordinator:
    return ShelterUpdateCoordinator(
        hass=mock_hass,
        cache=mock_cache,
        overpass_client=mock_overpass_client,
        persons=["person.alice"],
        search_radius=2000,
        adaptive_radius=True,
        adaptive_radius_max=15000,
    )

@pytest.mark.asyncio
async def test_fetch_from_overpass_when_cache_empty(coordinator, mock_overpass_client, mock_cache):
    data = await coordinator._async_update_data()
    mock_overpass_client.fetch_shelters.assert_called()
    mock_cache.save.assert_called_once()
    assert len(data) == 1

@pytest.mark.asyncio
async def test_use_cache_when_valid(coordinator, mock_cache, mock_overpass_client):
    mock_cache.is_valid = MagicMock(return_value=True)
    mock_cache.load.return_value = [
        {"osm_id": "node/1", "name": "Cached", "latitude": 48.85, "longitude": 2.35, "shelter_type": "bunker", "source": "osm"},
    ]
    data = await coordinator._async_update_data()
    mock_overpass_client.fetch_shelters.assert_not_called()
    assert data[0]["name"] == "Cached"

@pytest.mark.asyncio
async def test_merge_pois(coordinator, mock_cache, mock_overpass_client):
    mock_cache.load_pois.return_value = [
        {"id": "poi1", "name": "Ma Cave", "latitude": 48.86, "longitude": 2.36, "shelter_type": "bunker", "source": "manual"},
    ]
    data = await coordinator._async_update_data()
    assert len(data) == 2
    assert any(s["name"] == "Ma Cave" for s in data)

@pytest.mark.asyncio
async def test_fallback_to_stale_cache_on_error(coordinator, mock_cache, mock_overpass_client):
    mock_overpass_client.fetch_shelters = AsyncMock(side_effect=Exception("API down"))
    stale_data = [{"osm_id": "node/1", "name": "Stale", "latitude": 48.85, "longitude": 2.35, "shelter_type": "shelter", "source": "osm"}]
    mock_cache.load_stale.return_value = stale_data
    data = await coordinator._async_update_data()
    assert data[0]["name"] == "Stale"

@pytest.mark.asyncio
async def test_error_with_no_cache_raises(coordinator, mock_cache, mock_overpass_client):
    mock_overpass_client.fetch_shelters = AsyncMock(side_effect=Exception("API down"))
    mock_cache.load_stale.return_value = []
    with pytest.raises(Exception):
        await coordinator._async_update_data()
