"""Tests for AlertProvider base class and GouvAlert dataclass."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from custom_components.shelter_finder.alert_providers.base import (
    AlertProvider,
    GouvAlert,
    meets_min_severity,
)


def test_gouv_alert_construction():
    alert = GouvAlert(
        alert_id="gr-42",
        threat_type="flood",
        severity="severe",
        title="Crue de la Seine",
        message="Inondation imminente",
        source="georisques",
        zone_lat=48.85,
        zone_lon=2.35,
        starts_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        expires_at=None,
    )
    assert alert.alert_id == "gr-42"
    assert alert.threat_type == "flood"
    assert alert.source == "georisques"


def test_meets_min_severity_true():
    assert meets_min_severity("severe", "moderate") is True
    assert meets_min_severity("extreme", "severe") is True
    assert meets_min_severity("severe", "severe") is True


def test_meets_min_severity_false():
    assert meets_min_severity("minor", "severe") is False
    assert meets_min_severity("moderate", "severe") is False


def test_meets_min_severity_unknown_treated_as_minor():
    # Unknown input severity must not slip through a severe threshold
    assert meets_min_severity("weird", "severe") is False


def test_alert_provider_is_abstract():
    with pytest.raises(TypeError):
        AlertProvider()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_subclass_works():
    class _Stub(AlertProvider):
        source_name = "stub"

        async def async_fetch_alerts(self, lat, lon, radius_km):
            return []

    stub = _Stub()
    result = await stub.async_fetch_alerts(48.85, 2.35, 5.0)
    assert result == []
    assert stub.source_name == "stub"
