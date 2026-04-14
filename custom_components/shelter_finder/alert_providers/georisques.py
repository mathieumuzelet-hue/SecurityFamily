"""Georisques (gouv.fr) alert provider."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .base import AlertProvider, GouvAlert

_LOGGER = logging.getLogger(__name__)

GEORISQUES_BASE_URL = "https://georisques.gouv.fr/api/v1"
HTTP_TIMEOUT_SECONDS = 10

# Georisques returns severity as a French label ("faible", "moyen", "fort",
# "tres_fort") or a numeric code ("1".."4"). SEVERITY_RANK in the coordinator
# only knows the English labels ("minor", "moderate", "severe", "extreme"),
# so without normalization every Georisques alert is filtered out at the
# default min_severity. Map FR -> EN; unknown values fall through unchanged.
_FR_SEVERITY_MAP = {
    "faible": "minor",
    "moyen": "moderate",
    "fort": "severe",
    "tres_fort": "extreme",
    "très_fort": "extreme",
    "1": "minor",
    "2": "moderate",
    "3": "severe",
    "4": "extreme",
}


def _map_risque_to_threat(risque: str) -> str | None:
    """Map a Georisques `risque` label/code to a Shelter Finder threat_type."""
    if not risque:
        return None
    upper = risque.upper()
    if "INONDATION" in upper:
        return "flood"
    if "SEISME" in upper or "SÉISME" in risque.upper():
        return "earthquake"
    if upper in {"INDUSTRIEL"} or "ICPE" in upper or "SEVESO" in upper:
        return "nuclear_chemical"
    return None


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    # Normalize trailing Z to +00:00 for fromisoformat
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class GeorisquesProvider(AlertProvider):
    """Fetches active risks from the public Georisques GASPAR API."""

    source_name = "georisques"

    def __init__(self, session: Any) -> None:
        self._session = session

    async def async_fetch_alerts(
        self, lat: float, lon: float, radius_km: float
    ) -> list[GouvAlert]:
        url = f"{GEORISQUES_BASE_URL}/gaspar/risques"
        # Georisques expects lon,lat order for latlon
        params = {"latlon": f"{lon},{lat}", "rayon": int(max(1, round(radius_km)))}
        try:
            async with self._session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Georisques HTTP %s for %s", resp.status, url)
                    return []
                payload: dict[str, Any] = await resp.json()
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.debug("Georisques fetch failed: %s", err)
            return []

        alerts: list[GouvAlert] = []
        for item in payload.get("data", []) or []:
            risque = item.get("risque") or ""
            threat = _map_risque_to_threat(risque)
            if threat is None:
                continue
            raw_id = item.get("id_gaspar") or item.get("id")
            if not raw_id:
                continue
            starts = _parse_iso8601(item.get("date_debut")) or datetime.now(timezone.utc)
            expires = _parse_iso8601(item.get("date_fin"))
            try:
                zone_lat = float(item.get("latitude"))
                zone_lon = float(item.get("longitude"))
            except (TypeError, ValueError):
                continue
            raw = (item.get("niveau") or "moyen").lower()
            severity = _FR_SEVERITY_MAP.get(raw, raw)
            alerts.append(
                GouvAlert(
                    alert_id=f"georisques:{raw_id}",
                    threat_type=threat,
                    severity=severity,
                    title=item.get("libelle") or risque,
                    message=item.get("description") or "",
                    source="georisques",
                    zone_lat=zone_lat,
                    zone_lon=zone_lon,
                    starts_at=starts,
                    expires_at=expires,
                )
            )
        return alerts
