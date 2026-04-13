"""Tests for Shelter Finder Overpass client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from custom_components.shelter_finder.overpass import OverpassClient, build_overpass_query, _parse_element

SAMPLE_OVERPASS_RESPONSE = {
    "elements": [
        {"type": "node", "id": 123456, "lat": 48.8566, "lon": 2.3522, "tags": {"amenity": "shelter", "name": "Abri du Parc"}},
        {"type": "node", "id": 789012, "lat": 48.8600, "lon": 2.3400, "tags": {"building": "bunker", "name": "Bunker Souterrain"}},
        {"type": "way", "id": 345678, "center": {"lat": 48.8550, "lon": 2.3480}, "tags": {"railway": "station", "name": "Gare du Nord"}},
    ],
}

def test_build_overpass_query() -> None:
    tags = ["amenity=shelter", "building=bunker"]
    query = build_overpass_query(48.85, 2.35, 2000, tags)
    assert "around:2000,48.85,2.35" in query
    assert 'node["amenity"="shelter"]' in query
    assert 'way["amenity"="shelter"]' in query
    assert 'node["building"="bunker"]' in query
    assert "[out:json]" in query
    assert "out center;" in query

def test_build_overpass_query_wildcard() -> None:
    tags = ["shelter_type=*"]
    query = build_overpass_query(48.85, 2.35, 2000, tags)
    assert 'node["shelter_type"]' in query
    assert 'way["shelter_type"]' in query

@pytest.mark.asyncio
async def test_fetch_shelters_success() -> None:
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=SAMPLE_OVERPASS_RESPONSE)
    mock_response.raise_for_status = AsyncMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    mock_session.post = AsyncMock(return_value=mock_response)

    client = OverpassClient(session=mock_session)
    shelters = await client.fetch_shelters(48.85, 2.35, 2000)

    assert len(shelters) == 3
    assert shelters[0]["name"] == "Abri du Parc"
    assert shelters[0]["latitude"] == 48.8566
    assert shelters[0]["longitude"] == 2.3522
    assert shelters[0]["shelter_type"] == "shelter"
    assert shelters[0]["source"] == "osm"
    assert shelters[2]["latitude"] == 48.8550

@pytest.mark.asyncio
async def test_fetch_shelters_empty_response() -> None:
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"elements": []})
    mock_response.raise_for_status = AsyncMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    mock_session.post = AsyncMock(return_value=mock_response)

    client = OverpassClient(session=mock_session)
    shelters = await client.fetch_shelters(48.85, 2.35, 2000)
    assert shelters == []

def test_parse_element_node() -> None:
    element = {"type": "node", "id": 123, "lat": 48.85, "lon": 2.35, "tags": {"amenity": "shelter", "name": "Test Shelter"}}
    result = _parse_element(element)
    assert result is not None
    assert result["osm_id"] == "node/123"
    assert result["name"] == "Test Shelter"
    assert result["shelter_type"] == "shelter"
    assert result["source"] == "osm"

def test_parse_element_no_name() -> None:
    element = {"type": "node", "id": 456, "lat": 48.86, "lon": 2.36, "tags": {"building": "bunker"}}
    result = _parse_element(element)
    assert result is not None
    assert result["name"] == "bunker"
