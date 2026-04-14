"""Tests for MeteoFranceProvider.

Uses a fake session (not aiohttp.ClientSession + aioresponses) to avoid
aiohttp's threaded DNS resolver leaking into verify_cleanup.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from custom_components.shelter_finder.alert_providers.meteo_france import (
    METEO_FRANCE_URL,
    MeteoFranceProvider,
    _color_to_severity,
    _map_phenomenon_to_threat,
    _nearby_department_codes,
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
        self.calls: list[str] = []

    def get(self, url: str, *, timeout=None, **_) -> _FakeGetCtx:
        self.calls.append(url)
        if self._exception is not None:
            return _FakeGetCtx(None, self._exception)
        return _FakeGetCtx(_FakeResponse(status=self._status, payload=self._payload), None)


def test_color_to_severity():
    assert _color_to_severity("rouge") == "extreme"
    assert _color_to_severity("orange") == "severe"
    assert _color_to_severity("jaune") == "minor"
    assert _color_to_severity("vert") is None
    assert _color_to_severity("unknown") is None


def test_map_phenomenon_to_threat():
    assert _map_phenomenon_to_threat("vent") == "storm"
    assert _map_phenomenon_to_threat("Vent violent") == "storm"
    assert _map_phenomenon_to_threat("orages") == "storm"
    assert _map_phenomenon_to_threat("pluie-inondation") == "flood"
    # v0.6.1: snow/ice and heatwave now map to storm (closest response pattern).
    assert _map_phenomenon_to_threat("neige") == "storm"
    assert _map_phenomenon_to_threat("neige-verglas") == "storm"
    assert _map_phenomenon_to_threat("canicule") == "storm"
    assert _map_phenomenon_to_threat("phenomene inconnu") is None


def test_nearby_departments_paris():
    # Paris is 75, close to 92/93/94/77/78/91/95
    codes = _nearby_department_codes(48.85, 2.35, radius_km=20)
    assert "75" in codes


@pytest.mark.asyncio
async def test_fetch_alerts_parses_vigilance():
    payload = {
        "product": {
            "periods": [
                {
                    "text_bloc_items": [],
                    "timelaps": {
                        "domain_ids": [
                            {
                                "domain_id": "75",
                                "phenomenon_items": [
                                    {
                                        "phenomenon_id": "6",
                                        "phenomenon_name": "pluie-inondation",
                                        "phenomenon_max_color_id": 3,
                                        "phenomenon_max_color_name": "orange",
                                    },
                                    {
                                        "phenomenon_id": "2",
                                        "phenomenon_name": "vent",
                                        "phenomenon_max_color_id": 4,
                                        "phenomenon_max_color_name": "rouge",
                                    },
                                ],
                            },
                            {
                                "domain_id": "13",  # far (Marseille) — filtered
                                "phenomenon_items": [
                                    {
                                        "phenomenon_id": "2",
                                        "phenomenon_name": "vent",
                                        "phenomenon_max_color_name": "rouge",
                                    }
                                ],
                            },
                        ]
                    },
                    "begin_validity_time": "2026-04-14T06:00:00Z",
                    "end_validity_time": "2026-04-14T22:00:00Z",
                }
            ]
        }
    }

    session = _FakeSession(payload=payload)
    provider = MeteoFranceProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 20.0)

    assert len(alerts) == 2
    alerts_by_threat = {a.threat_type: a for a in alerts}
    assert "flood" in alerts_by_threat
    assert "storm" in alerts_by_threat
    flood = alerts_by_threat["flood"]
    assert flood.source == "meteo_france"
    assert flood.severity == "severe"
    assert flood.alert_id == "meteo_france:75:pluie-inondation:2026-04-14T06:00:00+00:00"
    assert flood.starts_at == datetime(2026, 4, 14, 6, 0, tzinfo=timezone.utc)
    assert flood.expires_at == datetime(2026, 4, 14, 22, 0, tzinfo=timezone.utc)
    storm = alerts_by_threat["storm"]
    assert storm.severity == "extreme"
    assert session.calls == [METEO_FRANCE_URL]


@pytest.mark.asyncio
async def test_fetch_alerts_http_error_returns_empty():
    session = _FakeSession(status=503)
    provider = MeteoFranceProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 20.0)
    assert alerts == []


@pytest.mark.asyncio
async def test_fetch_alerts_green_department_yields_no_alerts():
    payload = {
        "product": {
            "periods": [
                {
                    "timelaps": {
                        "domain_ids": [
                            {
                                "domain_id": "75",
                                "phenomenon_items": [
                                    {
                                        "phenomenon_name": "vent",
                                        "phenomenon_max_color_name": "vert",
                                    }
                                ],
                            }
                        ]
                    },
                    "begin_validity_time": "2026-04-14T06:00:00Z",
                    "end_validity_time": "2026-04-14T22:00:00Z",
                }
            ]
        }
    }
    session = _FakeSession(payload=payload)
    provider = MeteoFranceProvider(session=session)
    alerts = await provider.async_fetch_alerts(48.85, 2.35, 20.0)
    assert alerts == []
