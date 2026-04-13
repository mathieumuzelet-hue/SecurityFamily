"""Overpass API client for fetching shelter data from OpenStreetMap."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import DEFAULT_OSM_TAGS, DEFAULT_OVERPASS_URL, OSM_TAG_TO_SHELTER_TYPE

_LOGGER = logging.getLogger(__name__)


def build_overpass_query(lat: float, lon: float, radius: int, tags: list[str]) -> str:
    union_parts = []
    for tag in tags:
        key, _, value = tag.partition("=")
        if value == "*" or value == "":
            filter_str = f'["{key}"]'
        else:
            filter_str = f'["{key}"="{value}"]'
        around = f"(around:{radius},{lat},{lon})"
        union_parts.append(f"  node{filter_str}{around};")
        union_parts.append(f"  way{filter_str}{around};")
    union_body = "\n".join(union_parts)
    return f"[out:json][timeout:25];\n(\n{union_body}\n);\nout center;"


def _determine_shelter_type(tags: dict[str, str]) -> str:
    for osm_tag, shelter_type in OSM_TAG_TO_SHELTER_TYPE.items():
        key, _, value = osm_tag.partition("=")
        if key in tags and (value == "*" or tags[key] == value):
            return shelter_type
    return "shelter"


def _parse_element(element: dict[str, Any]) -> dict[str, Any] | None:
    tags = element.get("tags", {})
    element_type = element.get("type", "node")
    element_id = element.get("id", 0)
    if element_type == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    elif element_type == "way" and "center" in element:
        lat = element["center"].get("lat")
        lon = element["center"].get("lon")
    else:
        return None
    if lat is None or lon is None:
        return None
    shelter_type = _determine_shelter_type(tags)
    name = tags.get("name", shelter_type)
    return {
        "osm_id": f"{element_type}/{element_id}",
        "name": name,
        "latitude": lat,
        "longitude": lon,
        "shelter_type": shelter_type,
        "source": "osm",
        "address": tags.get("addr:street", ""),
    }


class OverpassClient:
    def __init__(self, session: aiohttp.ClientSession, url: str = DEFAULT_OVERPASS_URL, tags: list[str] | None = None) -> None:
        self._session = session
        self._url = url
        self._tags = tags or DEFAULT_OSM_TAGS

    async def fetch_shelters(self, lat: float, lon: float, radius: int) -> list[dict[str, Any]]:
        query = build_overpass_query(lat, lon, radius, self._tags)
        resp_cm = await self._session.post(self._url, data={"data": query})
        async with resp_cm as resp:
            await resp.raise_for_status()
            data = await resp.json()
        elements = data.get("elements", [])
        shelters = []
        for element in elements:
            parsed = _parse_element(element)
            if parsed is not None:
                shelters.append(parsed)
        return shelters
