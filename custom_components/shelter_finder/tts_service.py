"""TTS announcement service for Shelter Finder."""

from __future__ import annotations

import logging
from typing import Any

from .const import THREAT_LABELS_FR

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
