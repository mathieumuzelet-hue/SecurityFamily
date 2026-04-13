"""Fixtures for Shelter Finder tests."""

from __future__ import annotations

import pytest

try:
    pytest_plugins = "pytest_homeassistant_custom_component"
    import pytest_homeassistant_custom_component  # noqa: F401
    _HA_PLUGIN_AVAILABLE = True
except ImportError:
    _HA_PLUGIN_AVAILABLE = False


if _HA_PLUGIN_AVAILABLE:
    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Enable custom integrations in all tests."""
        yield
else:
    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations():
        """No-op stub when HA test plugin is unavailable."""
        yield


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
