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

    # Trigger on every configured entry; webhook is domain-wide.
    triggered = 0
    for value in hass.data.get(DOMAIN, {}).values():
        if not isinstance(value, dict):
            continue
        ac = value.get("alert_coordinator")
        if ac is None:
            continue
        ac.trigger(threat_type, triggered_by=f"webhook:{source}")
        triggered += 1

    if triggered == 0:
        return Response(status=500, text="Shelter Finder not initialized")
    return Response(status=200, text="Alert triggered")
