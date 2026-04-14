"""Base classes for FR-Alert / SAIP providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from ..const import SEVERITY_RANK


def parse_iso8601(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp, normalizing trailing Z and adding UTC.

    Returns None for falsy input or unparseable strings. Naive datetimes
    are forced to UTC so downstream comparisons are tz-aware.
    """
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class GouvAlert:
    """A normalized government alert from a French source."""

    alert_id: str
    threat_type: str
    severity: str
    title: str
    message: str
    source: str
    zone_lat: float
    zone_lon: float
    starts_at: datetime
    expires_at: datetime | None


def meets_min_severity(severity: str, minimum: str) -> bool:
    """Return True if `severity` is >= `minimum` on the SEVERITY_LEVELS scale.

    Unknown severity strings are treated as the lowest rank (-1) so they cannot
    accidentally satisfy a threshold.
    """
    actual = SEVERITY_RANK.get(severity, -1)
    threshold = SEVERITY_RANK.get(minimum, -1)
    return actual >= threshold


class AlertProvider(ABC):
    """Abstract provider that fetches normalized GouvAlert objects."""

    source_name: str = "unknown"

    @abstractmethod
    async def async_fetch_alerts(
        self, lat: float, lon: float, radius_km: float
    ) -> list[GouvAlert]:
        """Fetch current alerts near (lat, lon) within radius_km."""
