"""Tests for ShelterUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.shelter_finder.coordinator import ShelterUpdateCoordinator


def _state(lat: float | None, lon: float | None) -> MagicMock:
    state = MagicMock()
    state.attributes = {"latitude": lat, "longitude": lon}
    return state


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
        {"id": "node/1", "osm_id": "node/1", "name": "Abri Test",
         "latitude": 48.85, "longitude": 2.35,
         "shelter_type": "shelter", "source": "osm"},
    ])
    return client


_UNSET = object()


def _make_hass(person_states: dict[str, MagicMock | None] | None = None,
               home=_UNSET) -> MagicMock:
    hass = MagicMock()
    home_state = _state(48.85, 2.35) if home is _UNSET else home
    states_map: dict[str, MagicMock | None] = {"zone.home": home_state}
    if person_states:
        states_map.update(person_states)
    hass.states.get.side_effect = lambda entity_id: states_map.get(entity_id)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *args: fn(*args))
    return hass


@pytest.fixture
def mock_hass() -> MagicMock:
    # Default fixture: one person co-located with zone.home so legacy tests behave.
    return _make_hass({"person.alice": _state(48.85, 2.35)})


def _make_coordinator(hass, cache, overpass, persons=None) -> ShelterUpdateCoordinator:
    with patch("custom_components.shelter_finder.coordinator.DataUpdateCoordinator.__init__"):
        coord = ShelterUpdateCoordinator(
            hass=hass,
            cache=cache,
            overpass_client=overpass,
            persons=persons if persons is not None else ["person.alice"],
            search_radius=2000,
            adaptive_radius=True,
            adaptive_radius_max=15000,
        )
        coord.hass = hass
        coord.logger = MagicMock()
        return coord


@pytest.fixture
def coordinator(mock_hass, mock_cache, mock_overpass_client) -> ShelterUpdateCoordinator:
    return _make_coordinator(mock_hass, mock_cache, mock_overpass_client)


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


# --- v0.6.2: per-person refresh ---------------------------------------------


@pytest.mark.asyncio
async def test_fetch_queries_each_person_location(mock_cache, mock_overpass_client):
    hass = _make_hass({
        "person.alice": _state(48.85, 2.35),
        "person.bob": _state(43.60, 1.44),
    })
    # Enough results per-person to skip adaptive widening.
    # Spread coordinates so the haversine dedupe in merge_shelters_and_pois
    # (50m threshold) does not collapse them.
    mock_overpass_client.fetch_shelters = AsyncMock(side_effect=[
        [{"id": f"node/a{i}", "latitude": 48.85 + i * 0.01, "longitude": 2.35,
          "shelter_type": "shelter", "source": "osm"} for i in range(3)],
        [{"id": f"node/b{i}", "latitude": 43.60 + i * 0.01, "longitude": 1.44,
          "shelter_type": "shelter", "source": "osm"} for i in range(3)],
    ])
    coord = _make_coordinator(
        hass, mock_cache, mock_overpass_client,
        persons=["person.alice", "person.bob"],
    )

    data = await coord._async_update_data()

    assert mock_overpass_client.fetch_shelters.await_count == 2
    called_coords = {
        (call.args[0], call.args[1])
        for call in mock_overpass_client.fetch_shelters.call_args_list
    }
    assert (48.85, 2.35) in called_coords
    assert (43.60, 1.44) in called_coords
    assert len(data) == 6


@pytest.mark.asyncio
async def test_fetch_merges_and_deduplicates(mock_cache, mock_overpass_client):
    hass = _make_hass({
        "person.alice": _state(48.85, 2.35),
        "person.bob": _state(48.86, 2.36),
    })
    shared = {"id": "node/shared", "latitude": 48.855, "longitude": 2.355,
              "shelter_type": "shelter", "source": "osm"}
    alice_only = {"id": "node/alice", "latitude": 48.85, "longitude": 2.35,
                  "shelter_type": "shelter", "source": "osm"}
    bob_only = {"id": "node/bob", "latitude": 48.86, "longitude": 2.36,
                "shelter_type": "shelter", "source": "osm"}
    mock_overpass_client.fetch_shelters = AsyncMock(side_effect=[
        [shared, alice_only, {"id": "node/x", "latitude": 1, "longitude": 1,
                              "shelter_type": "shelter", "source": "osm"}],
        [shared, bob_only, {"id": "node/y", "latitude": 2, "longitude": 2,
                            "shelter_type": "shelter", "source": "osm"}],
    ])
    coord = _make_coordinator(
        hass, mock_cache, mock_overpass_client,
        persons=["person.alice", "person.bob"],
    )

    data = await coord._async_update_data()

    ids = [s.get("id") for s in data]
    assert ids.count("node/shared") == 1
    assert "node/alice" in ids
    assert "node/bob" in ids


@pytest.mark.asyncio
async def test_fetch_skips_person_without_location(mock_cache, mock_overpass_client):
    hass = _make_hass({
        "person.alice": _state(48.85, 2.35),
        "person.bob": None,  # tracker off
    })
    mock_overpass_client.fetch_shelters = AsyncMock(return_value=[
        {"id": f"node/{i}", "latitude": 48.85, "longitude": 2.35,
         "shelter_type": "shelter", "source": "osm"} for i in range(3)
    ])
    coord = _make_coordinator(
        hass, mock_cache, mock_overpass_client,
        persons=["person.alice", "person.bob"],
    )

    await coord._async_update_data()

    assert mock_overpass_client.fetch_shelters.await_count == 1
    assert mock_overpass_client.fetch_shelters.call_args.args[:2] == (48.85, 2.35)


@pytest.mark.asyncio
async def test_fetch_falls_back_to_zone_home_when_no_person_has_location(
    mock_cache, mock_overpass_client,
):
    hass = _make_hass(
        {"person.alice": _state(None, None), "person.bob": None},
        home=_state(49.00, 2.50),
    )
    mock_overpass_client.fetch_shelters = AsyncMock(return_value=[
        {"id": f"node/{i}", "latitude": 49.00, "longitude": 2.50,
         "shelter_type": "shelter", "source": "osm"} for i in range(3)
    ])
    coord = _make_coordinator(
        hass, mock_cache, mock_overpass_client,
        persons=["person.alice", "person.bob"],
    )

    await coord._async_update_data()

    assert mock_overpass_client.fetch_shelters.await_count == 1
    assert mock_overpass_client.fetch_shelters.call_args.args[:2] == (49.00, 2.50)


@pytest.mark.asyncio
async def test_fetch_raises_when_no_location_available(mock_cache, mock_overpass_client):
    hass = _make_hass({"person.alice": None}, home=None)
    coord = _make_coordinator(
        hass, mock_cache, mock_overpass_client, persons=["person.alice"],
    )

    with pytest.raises(Exception):
        await coord._async_update_data()

    mock_overpass_client.fetch_shelters.assert_not_called()
