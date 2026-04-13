"""Fixtures for Shelter Finder tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_persons() -> list[str]:
    """Return test person entity IDs."""
    return ["person.alice", "person.bob"]


@pytest.fixture
def mock_config_entry_data(mock_persons: list[str]) -> dict:
    """Return mock config entry data."""
    return {
        "persons": mock_persons,
        "search_radius": 2000,
        "language": "fr",
        "enabled_threats": [
            "storm",
            "earthquake",
            "attack",
            "armed_conflict",
            "flood",
            "nuclear_chemical",
        ],
        "default_travel_mode": "walking",
        "webhook_id": "sf_test_webhook_id",
    }
