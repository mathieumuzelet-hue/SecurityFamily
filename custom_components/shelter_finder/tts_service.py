"""TTS announcement service for Shelter Finder."""

from __future__ import annotations

import logging
from typing import Any

from .const import THREAT_LABELS_FR, TTS_SERVICE_CANDIDATES

_LOGGER = logging.getLogger(__name__)


def build_message(
    threat_type: str,
    shelter_name: str,
    distance_m: int,
    eta_minutes: int | None,
    is_drill: bool,
) -> str:
    """Build the French TTS message for a single shelter assignment.

    ASCII-only (no accents) for broad TTS engine compatibility.
    """
    label = THREAT_LABELS_FR.get(threat_type, threat_type)
    eta_str = "?" if eta_minutes is None else str(eta_minutes)
    body = (
        f"Alerte {label}. Dirigez-vous vers {shelter_name}, "
        f"a {int(distance_m)} metres, environ {eta_str} minutes a pied."
    )
    if is_drill:
        return f"Ceci est un exercice. {body}"
    return body


def resolve_tts_service(hass: Any, configured: str | None) -> str | None:
    """Return the TTS service name to use, or None if none available.

    Lookup order:
    1. `configured` (from options) if registered in the `tts` domain.
    2. First match in TTS_SERVICE_CANDIDATES that is registered.
    3. None — caller should log and skip TTS.
    """
    tts_services = hass.services.async_services().get("tts", {}) or {}
    if configured:
        if configured in tts_services:
            return configured
        _LOGGER.warning(
            "Configured TTS service tts.%s not found; falling back to auto-detect",
            configured,
        )
    for candidate in TTS_SERVICE_CANDIDATES:
        if candidate in tts_services:
            return candidate
    return None


_AVAILABLE_MEDIA_STATES = {"on", "idle", "playing", "paused"}


def resolve_targets(hass: Any, configured: list[str] | None) -> list[str]:
    """Return the list of media_player entity_ids to announce on.

    - If `configured` is non-empty, use it as-is (user's explicit choice).
    - Otherwise, scan all states and pick media_player entities whose state
      is in {on, idle, playing, paused}. "off" and "unavailable" are skipped.
    """
    if configured:
        return list(configured)
    targets: list[str] = []
    for state in hass.states.async_all():
        entity_id = getattr(state, "entity_id", "")
        if not entity_id.startswith("media_player."):
            continue
        if state.state in _AVAILABLE_MEDIA_STATES:
            targets.append(entity_id)
    return targets
