"""Meteo France vigilance alert provider (public JSON feed)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .._geo import haversine_km
from .base import AlertProvider, GouvAlert, parse_iso8601

_LOGGER = logging.getLogger(__name__)

METEO_FRANCE_URL = "https://vigilance.meteofrance.fr/data/vigilance.json"
HTTP_TIMEOUT_SECONDS = 10

# Department centroid table (code -> (lat, lon)). Metropolitan France + Corsica.
# Centroids are approximate; precision to 0.1 deg is sufficient because we
# buffer with `radius_km + 80km` to cover a whole department.
DEPARTMENT_CENTROIDS: dict[str, tuple[float, float]] = {
    "01": (46.20, 5.35), "02": (49.55, 3.55), "03": (46.40, 3.20),
    "04": (44.10, 6.25), "05": (44.65, 6.30), "06": (43.95, 7.15),
    "07": (44.75, 4.40), "08": (49.60, 4.65), "09": (42.95, 1.50),
    "10": (48.30, 4.15), "11": (43.10, 2.45), "12": (44.30, 2.75),
    "13": (43.55, 5.10), "14": (49.10, -0.35), "15": (45.05, 2.65),
    "16": (45.70, 0.15), "17": (45.75, -0.65), "18": (47.05, 2.50),
    "19": (45.35, 1.85), "21": (47.40, 4.80), "22": (48.40, -2.85),
    "23": (46.10, 2.05), "24": (45.10, 0.75), "25": (47.15, 6.40),
    "26": (44.70, 5.15), "27": (49.10, 0.95), "28": (48.45, 1.45),
    "29": (48.25, -4.05), "2A": (41.85, 8.90), "2B": (42.40, 9.20),
    "30": (44.05, 4.25), "31": (43.40, 1.45), "32": (43.65, 0.50),
    "33": (44.85, -0.55), "34": (43.60, 3.45), "35": (48.15, -1.65),
    "36": (46.80, 1.55), "37": (47.30, 0.75), "38": (45.25, 5.65),
    "39": (46.75, 5.65), "40": (43.95, -0.75), "41": (47.60, 1.45),
    "42": (45.65, 4.30), "43": (45.10, 3.85), "44": (47.30, -1.65),
    "45": (47.90, 2.25), "46": (44.60, 1.65), "47": (44.35, 0.65),
    "48": (44.50, 3.55), "49": (47.35, -0.55), "50": (49.10, -1.10),
    "51": (49.00, 4.35), "52": (48.10, 5.15), "53": (48.10, -0.65),
    "54": (48.70, 6.15), "55": (48.95, 5.40), "56": (47.85, -2.80),
    "57": (49.05, 6.60), "58": (47.05, 3.50), "59": (50.45, 3.15),
    "60": (49.40, 2.45), "61": (48.60, 0.15), "62": (50.45, 2.45),
    "63": (45.75, 3.15), "64": (43.25, -0.75), "65": (43.05, 0.15),
    "66": (42.60, 2.55), "67": (48.65, 7.65), "68": (47.95, 7.35),
    "69": (45.75, 4.70), "70": (47.65, 6.15), "71": (46.60, 4.50),
    "72": (48.00, 0.20), "73": (45.45, 6.65), "74": (46.00, 6.45),
    "75": (48.85, 2.35), "76": (49.65, 1.05), "77": (48.55, 3.05),
    "78": (48.80, 1.95), "79": (46.55, -0.25), "80": (49.95, 2.30),
    "81": (43.85, 2.15), "82": (44.05, 1.40), "83": (43.45, 6.25),
    "84": (44.00, 5.15), "85": (46.70, -1.40), "86": (46.55, 0.45),
    "87": (45.90, 1.25), "88": (48.20, 6.45), "89": (47.80, 3.55),
    "90": (47.65, 6.95), "91": (48.50, 2.25), "92": (48.85, 2.25),
    "93": (48.90, 2.50), "94": (48.80, 2.45), "95": (49.05, 2.15),
}

# Meteo France phenomenon -> Shelter Finder threat_type.
#
# Deliberately unmapped threats: "attack" and "armed_conflict" — no public
# French government feed currently exposes those categories, so they remain
# available only via manual / webhook / button triggers.
#
# "neige-verglas" (snow/ice) and "canicule" (heatwave) are mapped to "storm"
# because they share the same response pattern (shelter-in-place, avoid
# exposure) and the closest available shelter scoring profile. If a
# dedicated cold/heat threat type is ever added to THREAT_TYPES, these
# keywords should move accordingly.
_WIND_KEYWORDS = {"vent"}
_STORM_KEYWORDS = {"orages", "orage"}
_FLOOD_KEYWORDS = {"pluie-inondation", "inondation", "crues"}
_SNOW_KEYWORDS = {"neige-verglas", "neige", "verglas"}
_HEAT_KEYWORDS = {"canicule"}


def _nearby_department_codes(lat: float, lon: float, radius_km: float) -> set[str]:
    """Return department codes whose centroid is within radius_km + 80km buffer."""
    buffer = radius_km + 80.0
    return {
        code
        for code, (dlat, dlon) in DEPARTMENT_CENTROIDS.items()
        if haversine_km(lat, lon, dlat, dlon) <= buffer
    }


def _color_to_severity(color: str | None) -> str | None:
    if not color:
        return None
    c = color.lower()
    if c == "rouge":
        return "extreme"
    if c == "orange":
        return "severe"
    if c == "jaune":
        return "minor"
    return None


def _map_phenomenon_to_threat(name: str | None) -> str | None:
    if not name:
        return None
    n = name.lower()
    for kw in _FLOOD_KEYWORDS:
        if kw in n:
            return "flood"
    for kw in _STORM_KEYWORDS:
        if kw in n:
            return "storm"
    for kw in _WIND_KEYWORDS:
        if kw in n:
            return "storm"
    for kw in _SNOW_KEYWORDS:
        if kw in n:
            return "storm"
    for kw in _HEAT_KEYWORDS:
        if kw in n:
            return "storm"
    return None


class MeteoFranceProvider(AlertProvider):
    """Public Meteo France vigilance JSON feed."""

    source_name = "meteo_france"

    def __init__(self, session: Any) -> None:
        self._session = session

    async def async_fetch_alerts(
        self, lat: float, lon: float, radius_km: float
    ) -> list[GouvAlert]:
        try:
            async with self._session.get(
                METEO_FRANCE_URL,
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Meteo France HTTP %s", resp.status)
                    return []
                payload: dict[str, Any] = await resp.json()
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.debug("Meteo France fetch failed: %s", err)
            return []

        nearby = _nearby_department_codes(lat, lon, radius_km)
        alerts: list[GouvAlert] = []
        periods = payload.get("product", {}).get("periods", []) or []
        for period in periods:
            starts = parse_iso8601(period.get("begin_validity_time")) or datetime.now(timezone.utc)
            expires = parse_iso8601(period.get("end_validity_time"))
            starts_iso = starts.isoformat()
            domain_ids = (period.get("timelaps") or {}).get("domain_ids", []) or []
            for dom in domain_ids:
                dep = str(dom.get("domain_id") or "")
                if dep not in nearby:
                    continue
                dep_lat, dep_lon = DEPARTMENT_CENTROIDS[dep]
                for phen in dom.get("phenomenon_items", []) or []:
                    name = phen.get("phenomenon_name")
                    color = phen.get("phenomenon_max_color_name")
                    threat = _map_phenomenon_to_threat(name)
                    severity = _color_to_severity(color)
                    if threat is None or severity is None:
                        continue
                    alerts.append(
                        GouvAlert(
                            alert_id=f"meteo_france:{dep}:{name}:{starts_iso}",
                            threat_type=threat,
                            severity=severity,
                            title=f"Vigilance {color} {name} ({dep})",
                            message=f"Vigilance Meteo France {color} pour {name} sur le departement {dep}",
                            source="meteo_france",
                            zone_lat=dep_lat,
                            zone_lon=dep_lon,
                            starts_at=starts,
                            expires_at=expires,
                        )
                    )
        return alerts
