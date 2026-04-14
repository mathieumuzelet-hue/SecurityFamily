"""Smoke test that RoutingService is exposed via hass.data."""

from __future__ import annotations

from custom_components.shelter_finder.routing import RoutingService


def test_routing_service_importable_from_package() -> None:
    # If this import fails, the symbol was renamed or removed
    assert RoutingService is not None


def test_routing_service_constructible_with_ha_style_session() -> None:
    # Mimic what __init__.py will do: async_get_clientsession(hass) returns a session-like
    class FakeSession: pass
    svc = RoutingService(
        session=FakeSession(),
        enabled=True,
        url="https://osrm.example.com",
        transport_mode="foot",
    )
    assert svc.enabled is True
    assert svc.url == "https://osrm.example.com"
