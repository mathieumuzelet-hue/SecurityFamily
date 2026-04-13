"""Webhook handler for Shelter Finder."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.web import Request, Response

from .const import DOMAIN, THREAT_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_handle_webhook(hass: Any, webhook_id: str, request: Request) -> Response:
    try:
        data = await request.json()
    except Exception:
        return Response(status=400, text="Invalid JSON")

    threat_type = data.get("threat_type")
    if not threat_type:
        return Response(status=400, text="Missing required field: threat_type")

    if threat_type not in THREAT_TYPES:
        return Response(status=400, text=f"Unknown threat_type: {threat_type}. Valid: {', '.join(THREAT_TYPES)}")

    source = data.get("source", "unknown")

    alert_coordinator = hass.data.get(DOMAIN, {}).get("alert_coordinator")
    if alert_coordinator is None:
        return Response(status=500, text="Shelter Finder not initialized")

    alert_coordinator.trigger(threat_type, triggered_by=f"webhook:{source}")
    return Response(status=200, text="Alert triggered")
