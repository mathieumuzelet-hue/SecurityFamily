"""Tests for GeorisquesProvider.

Uses a fake session (not aiohttp.ClientSession + aioresponses) to avoid
aiohttp's threaded DNS resolver leaking into verify_cleanup.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiohttp
import pytest

from custom_components.shelter_finder.alert_providers.base import meets_min_severity
from custom_components.shelter_finder.alert_providers.georisques import (
    GEORISQUES_BASE_URL,
    GeorisquesProvider,
    _map_risque_to_threat,
)


class _FakeResponse:
    def __init__(self, *, status: int = 200, payload: Any = None) -> None:
        self.status = status
        self._payload = payload

    async def json(self) -> Any:
        return self._payload


class _FakeGetCtx:
    def __init__(self, response: _FakeResponse | None, exc: BaseException | None) -> None:
        self._response = response
        self._exc = exc

    async def __aenter__(self) -> _FakeResponse:
        if self._exc is not None:
            raise self._exc
        assert self._response is not None
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSession:
    def __init__(self, *, status: int = 200, payload: Any = None, exception: BaseException | None = None) -> None:
        self._status = status
        self._payload = payload
        self._exception = exception
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, *, params: dict | None = None, timeout=None) -> _FakeGetCtx:
        self.calls.append((url, params or {}))
        if self._exception is not None:
            return _FakeGetCtx(None, self._exception)
        return _FakeGetCtx(_FakeResponse(status=self._status, payload=self._payload), None)


def test_map_risque_to_threat_flood():
    assert _map_risque_to_threat("Inondation") == "flood"
    assert _map_risque_to_threat("INONDATION_CRUE") == "flood"


def test_map_risque_to_threat_earthquake():
    assert _map_risque_to_threat("Séisme") == "earthquake"
    assert _map_risque_to_threat("SEISME") == "earthquake"


def test_map_risque_to_threat_industrial():
    assert _map_risque_to_threat("Industriel") == "nuclear_chemical"
    assert _map_risque_to_threat("ICPE") == "nuclear_chemical"
    assert _map_risque_to_threat("SEVESO_HAUT") == "nuclear_chemical"


def test_map_risque_to_threat_unknown_returns_none():
    assert _map_risque_to_threat("Unknown") is None


@pytest.mark.asyncio
async def test_fetch_alerts_parses_response():
    payload = {
        "data": [
            {
                "id_gaspar": "GR-FLOOD-1",
                "risque": "Inondation",
                "niveau": "severe",
                "libelle": "Crue de la Seine",
                "description": "Inondation en cours",
                "latitude": 48.856,
                "longitude": 2.351,
                "date_debut": "2026-04-14T10:00:00Z",
                "date_fin": "2026-04-15T10:00:00Z",
            },
            {
                "id_gaspar": "GR-UNKNOWN-1",
                "risque": "Unknown",
                "niveau": "minor",
                "libelle": "Ignored",
                "description": "",
                "latitude": 48.86,
                "longitude": 2.35,
                "date_debut": "2026-04-14T10:00:00Z",
                "date_fin": None,
            },
        ]
    }

    session = _FakeSession(payload=payload)
    provider = GeorisquesProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)

    assert len(alerts) == 1
    a = alerts[0]
    assert a.alert_id == "georisques:GR-FLOOD-1"
    assert a.threat_type == "flood"
    assert a.severity == "severe"
    assert a.source == "georisques"
    assert a.zone_lat == 48.856
    assert a.zone_lon == 2.351
    assert a.starts_at == datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc)
    assert a.expires_at == datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    # Verify query shape
    assert session.calls[0][0] == f"{GEORISQUES_BASE_URL}/gaspar/risques"
    assert session.calls[0][1]["latlon"] == "2.35,48.85"
    assert session.calls[0][1]["rayon"] == 10


@pytest.mark.asyncio
async def test_fetch_alerts_http_error_returns_empty():
    session = _FakeSession(status=500, payload=None)
    provider = GeorisquesProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)
    assert alerts == []


@pytest.mark.asyncio
async def test_fetch_alerts_timeout_returns_empty():
    session = _FakeSession(exception=TimeoutError("boom"))
    provider = GeorisquesProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)
    assert alerts == []


@pytest.mark.asyncio
async def test_fetch_alerts_client_error_returns_empty():
    session = _FakeSession(exception=aiohttp.ClientError("boom"))
    provider = GeorisquesProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)
    assert alerts == []


@pytest.mark.asyncio
async def test_fetch_alerts_maps_french_severity_fort_to_severe():
    """Regression: Georisques returns FR severity labels ("fort"), which must
    map to the English label SEVERITY_RANK understands, otherwise the alert
    is silently filtered out at the default min_severity="severe"."""
    payload = {
        "data": [
            {
                "id_gaspar": "GR-FR-1",
                "risque": "Inondation",
                "niveau": "fort",
                "libelle": "Crue forte",
                "description": "",
                "latitude": 48.856,
                "longitude": 2.351,
                "date_debut": "2026-04-14T10:00:00Z",
                "date_fin": None,
            },
        ]
    }
    session = _FakeSession(payload=payload)
    provider = GeorisquesProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)

    assert len(alerts) == 1
    assert alerts[0].severity == "severe"
    # And the mapped value must survive the default min_severity gate.
    assert meets_min_severity(alerts[0].severity, "severe") is True


@pytest.mark.asyncio
async def test_fetch_alerts_maps_numeric_severity():
    payload = {
        "data": [
            {
                "id_gaspar": "GR-NUM-1",
                "risque": "Inondation",
                "niveau": "4",
                "libelle": "Crue extreme",
                "description": "",
                "latitude": 48.856,
                "longitude": 2.351,
                "date_debut": "2026-04-14T10:00:00Z",
                "date_fin": None,
            },
        ]
    }
    session = _FakeSession(payload=payload)
    provider = GeorisquesProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 10.0)
    assert len(alerts) == 1
    assert alerts[0].severity == "extreme"
