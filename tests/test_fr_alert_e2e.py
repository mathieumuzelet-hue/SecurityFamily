"""End-to-end FR-Alert pipeline test with a fake session.

Uses a fake session keyed by URL pattern (not aiohttp.ClientSession +
aioresponses) to avoid verify_cleanup thread leaks.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.shelter_finder.alert_provider_manager import AlertProviderManager
from custom_components.shelter_finder.alert_providers.georisques import (
    GEORISQUES_BASE_URL,
    GeorisquesProvider,
)
from custom_components.shelter_finder.alert_providers.meteo_france import (
    METEO_FRANCE_URL,
    MeteoFranceProvider,
)


class _FakeResponse:
    def __init__(self, *, status: int = 200, payload: Any = None) -> None:
        self.status = status
        self._payload = payload

    async def json(self) -> Any:
        return self._payload


class _FakeGetCtx:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _MultiRouteSession:
    """Routes by URL substring match."""

    def __init__(self) -> None:
        self._routes: list[tuple[str, Any]] = []
        self.calls: list[str] = []

    def add(self, url_substr: str, payload: Any) -> None:
        self._routes.append((url_substr, payload))

    def get(self, url: str, **_) -> _FakeGetCtx:
        self.calls.append(url)
        for substr, payload in self._routes:
            if substr in url:
                return _FakeGetCtx(_FakeResponse(status=200, payload=payload))
        raise AssertionError(f"Unexpected URL: {url}")


class _StubCoord:
    def __init__(self):
        self._active = False
        self._by = None
        self.trigger_calls = []
        self.cancel_calls = 0

    @property
    def is_active(self): return self._active
    @property
    def triggered_by(self): return self._by

    def trigger(self, threat_type, triggered_by="manual"):
        self._active = True
        self._by = triggered_by
        self.trigger_calls.append((threat_type, triggered_by))

    def cancel(self):
        self._active = False
        self._by = None
        self.cancel_calls += 1


@pytest.mark.asyncio
async def test_end_to_end_georisques_and_meteo_france():
    hass = MagicMock()
    zone = MagicMock()
    zone.attributes = {"latitude": 48.85, "longitude": 2.35}
    hass.states.get = MagicMock(return_value=zone)

    gr_payload = {
        "data": [
            {
                "id_gaspar": "CRUE-1",
                "risque": "Inondation",
                "niveau": "severe",
                "libelle": "Crue Seine",
                "description": "",
                "latitude": 48.86,
                "longitude": 2.34,
                "date_debut": "2026-04-14T08:00:00Z",
                "date_fin": None,
            }
        ]
    }
    mf_payload = {
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
                                        "phenomenon_max_color_name": "rouge",
                                    }
                                ],
                            }
                        ]
                    },
                    "begin_validity_time": "2026-04-14T06:00:00Z",
                    "end_validity_time": "2026-04-14T20:00:00Z",
                }
            ]
        }
    }

    session = _MultiRouteSession()
    session.add(GEORISQUES_BASE_URL, gr_payload)
    session.add(METEO_FRANCE_URL, mf_payload)

    coord = _StubCoord()
    callback_calls: list[int] = []
    mgr = AlertProviderManager(
        hass=hass,
        providers=[
            GeorisquesProvider(session=session),
            MeteoFranceProvider(session=session),
        ],
        alert_coordinator=coord,
        trigger_callback=lambda: callback_calls.append(1),
        polling_interval=60,
        radius_km=10.0,
        auto_cancel=True,
        min_severity="severe",
    )

    await mgr.async_poll_once()

    # First qualifying alert (either source) should trigger exactly one call.
    assert len(coord.trigger_calls) == 1
    threat, by = coord.trigger_calls[0]
    assert threat in {"flood", "storm"}
    assert by.startswith("provider:")
    assert callback_calls == [1]
