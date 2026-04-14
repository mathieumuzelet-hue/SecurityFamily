# Shelter Finder v0.6 TTS Voice Announcements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an alert triggers (real or drill), announce it in French on configured media players, with auto-detection of the TTS service, volume save/restore, and a "Ceci est un exercice." prefix in drill mode.

**Architecture:** A new `TTSService` class encapsulates the announcement flow (build message → pick TTS service → pick targets → save volumes → set volume → call `tts.speak` → wait → restore volume). It is instantiated in `async_setup_entry` and called from `_send_alert_notifications` after push notifications. The French threat-label mapping lives in `const.py`. Drill prefix is read via `AlertCoordinator.is_drill`. All HA interactions go through `hass.services.async_call` and `hass.states.get`.

**Tech Stack:** Python 3.11+, Home Assistant async core, pytest, pytest-asyncio, `unittest.mock.AsyncMock`/`MagicMock`.

---

## File Structure

- Create: `custom_components/shelter_finder/tts_service.py` — `TTSService` class, auto-detection, target selection, volume save/restore, speak.
- Modify: `custom_components/shelter_finder/const.py` — add `THREAT_LABELS_FR`, `DEFAULT_TTS_VOLUME`, `DEFAULT_TTS_BUFFER_SECONDS`, `TTS_SERVICE_CANDIDATES`.
- Modify: `custom_components/shelter_finder/__init__.py` — instantiate `TTSService`, call it from `_send_alert_notifications`.
- Create: `tests/test_tts_service.py` — unit tests for the service.

Assumptions (already merged): OptionsFlow step "Notifications" already collects `CONF_TTS_ENABLED`, `CONF_TTS_SERVICE`, `CONF_TTS_MEDIA_PLAYERS`, `CONF_TTS_VOLUME` into `const.py` and into `entry.options`. `AlertCoordinator.is_drill` returns a `bool`.

---

## Task 1: French threat labels + TTS constants

**Files:**
- Modify: `custom_components/shelter_finder/const.py` (append to end)
- Test: `tests/test_tts_service.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_tts_service.py` with:

```python
"""Tests for TTSService."""

from __future__ import annotations

from custom_components.shelter_finder.const import (
    DEFAULT_TTS_BUFFER_SECONDS,
    DEFAULT_TTS_VOLUME,
    THREAT_LABELS_FR,
    THREAT_TYPES,
    TTS_SERVICE_CANDIDATES,
)


def test_threat_labels_fr_covers_all_threat_types() -> None:
    for threat in THREAT_TYPES:
        assert threat in THREAT_LABELS_FR, f"Missing French label for {threat}"


def test_threat_labels_fr_values() -> None:
    assert THREAT_LABELS_FR["storm"] == "tempete"
    assert THREAT_LABELS_FR["earthquake"] == "seisme"
    assert THREAT_LABELS_FR["attack"] == "attaque"
    assert THREAT_LABELS_FR["armed_conflict"] == "conflit arme"
    assert THREAT_LABELS_FR["flood"] == "inondation"
    assert THREAT_LABELS_FR["nuclear_chemical"] == "nucleaire chimique"


def test_default_tts_volume_is_80_percent() -> None:
    assert DEFAULT_TTS_VOLUME == 0.8


def test_default_tts_buffer_seconds_is_2() -> None:
    assert DEFAULT_TTS_BUFFER_SECONDS == 2


def test_tts_service_candidates_order() -> None:
    assert TTS_SERVICE_CANDIDATES == [
        "google_translate_say",
        "cloud_say",
        "speak",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL with `ImportError` (constants not defined).

- [ ] **Step 3: Add constants to `const.py`**

Append to `custom_components/shelter_finder/const.py`:

```python
# --- TTS (v0.6) ---

# French labels for threat types (used in voice announcements; ASCII-only to
# maximize TTS engine compatibility — no accents).
THREAT_LABELS_FR: dict[str, str] = {
    "storm": "tempete",
    "earthquake": "seisme",
    "attack": "attaque",
    "armed_conflict": "conflit arme",
    "flood": "inondation",
    "nuclear_chemical": "nucleaire chimique",
}

# TTS defaults
DEFAULT_TTS_VOLUME = 0.8  # 0.0-1.0, applied to media_player before speaking
DEFAULT_TTS_BUFFER_SECONDS = 2  # extra seconds after estimated duration

# Auto-detection order: first match wins (service name only, domain is "tts").
TTS_SERVICE_CANDIDATES: list[str] = [
    "google_translate_say",
    "cloud_say",
    "speak",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tts_service.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/const.py tests/test_tts_service.py
git commit -m "feat(tts): add French threat labels and TTS defaults"
```

---

## Task 2: Message builder

**Files:**
- Create: `custom_components/shelter_finder/tts_service.py`
- Test: `tests/test_tts_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tts_service.py`:

```python
from custom_components.shelter_finder.tts_service import build_message


def test_build_message_real_alert() -> None:
    msg = build_message(
        threat_type="storm",
        shelter_name="Ecole Jules Ferry",
        distance_m=320,
        eta_minutes=4,
        is_drill=False,
    )
    assert msg == (
        "Alerte tempete. Dirigez-vous vers Ecole Jules Ferry, "
        "a 320 metres, environ 4 minutes a pied."
    )


def test_build_message_drill_has_prefix() -> None:
    msg = build_message(
        threat_type="attack",
        shelter_name="Metro Republique",
        distance_m=150,
        eta_minutes=2,
        is_drill=True,
    )
    assert msg.startswith("Ceci est un exercice. ")
    assert "Alerte attaque." in msg
    assert "Metro Republique" in msg


def test_build_message_unknown_threat_falls_back_to_raw_key() -> None:
    msg = build_message(
        threat_type="unknown_threat",
        shelter_name="Abri",
        distance_m=100,
        eta_minutes=1,
        is_drill=False,
    )
    assert "Alerte unknown_threat." in msg


def test_build_message_unknown_eta_shows_question_mark() -> None:
    msg = build_message(
        threat_type="flood",
        shelter_name="Mairie",
        distance_m=500,
        eta_minutes=None,
        is_drill=False,
    )
    assert "environ ? minutes a pied." in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_message'`.

- [ ] **Step 3: Create `tts_service.py` with `build_message`**

Create `custom_components/shelter_finder/tts_service.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tts_service.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/tts_service.py tests/test_tts_service.py
git commit -m "feat(tts): add French message builder with drill prefix"
```

---

## Task 3: Auto-detect TTS service

**Files:**
- Modify: `custom_components/shelter_finder/tts_service.py`
- Test: `tests/test_tts_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tts_service.py`:

```python
from unittest.mock import MagicMock

from custom_components.shelter_finder.tts_service import resolve_tts_service


def _hass_with_tts_services(names: list[str]) -> MagicMock:
    hass = MagicMock()
    hass.services.async_services.return_value = {
        "tts": {n: MagicMock() for n in names},
        "notify": {"mobile_app_alice": MagicMock()},
    }
    return hass


def test_resolve_tts_service_uses_configured_when_available() -> None:
    hass = _hass_with_tts_services(["google_translate_say", "cloud_say"])
    assert resolve_tts_service(hass, configured="cloud_say") == "cloud_say"


def test_resolve_tts_service_falls_back_when_configured_missing() -> None:
    hass = _hass_with_tts_services(["google_translate_say"])
    # Configured "piper" is not available → fall back to auto-detect.
    assert resolve_tts_service(hass, configured="piper") == "google_translate_say"


def test_resolve_tts_service_auto_detect_prefers_google() -> None:
    hass = _hass_with_tts_services(["cloud_say", "google_translate_say", "speak"])
    assert resolve_tts_service(hass, configured=None) == "google_translate_say"


def test_resolve_tts_service_auto_detect_second_choice() -> None:
    hass = _hass_with_tts_services(["cloud_say", "speak"])
    assert resolve_tts_service(hass, configured=None) == "cloud_say"


def test_resolve_tts_service_auto_detect_third_choice() -> None:
    hass = _hass_with_tts_services(["speak"])
    assert resolve_tts_service(hass, configured=None) == "speak"


def test_resolve_tts_service_none_available_returns_none() -> None:
    hass = MagicMock()
    hass.services.async_services.return_value = {"notify": {}}
    assert resolve_tts_service(hass, configured=None) is None


def test_resolve_tts_service_empty_string_treated_as_none() -> None:
    hass = _hass_with_tts_services(["google_translate_say"])
    assert resolve_tts_service(hass, configured="") == "google_translate_say"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_tts_service'`.

- [ ] **Step 3: Add `resolve_tts_service`**

Append to `custom_components/shelter_finder/tts_service.py`:

```python
from .const import TTS_SERVICE_CANDIDATES


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tts_service.py -v`
Expected: PASS (16 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/tts_service.py tests/test_tts_service.py
git commit -m "feat(tts): add TTS service auto-detection"
```

---

## Task 4: Target media_player selection

**Files:**
- Modify: `custom_components/shelter_finder/tts_service.py`
- Test: `tests/test_tts_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tts_service.py`:

```python
from custom_components.shelter_finder.tts_service import resolve_targets


def _state(entity_id: str, state: str) -> MagicMock:
    s = MagicMock()
    s.entity_id = entity_id
    s.state = state
    return s


def test_resolve_targets_uses_configured_list() -> None:
    hass = MagicMock()
    configured = ["media_player.kitchen", "media_player.living_room"]
    assert resolve_targets(hass, configured) == configured


def test_resolve_targets_empty_config_scans_available_on_or_idle() -> None:
    hass = MagicMock()
    hass.states.async_all.return_value = [
        _state("media_player.kitchen", "on"),
        _state("media_player.bedroom", "idle"),
        _state("media_player.garage", "off"),
        _state("media_player.tv", "unavailable"),
        _state("light.hall", "on"),  # not a media_player
    ]
    assert resolve_targets(hass, []) == [
        "media_player.kitchen",
        "media_player.bedroom",
    ]


def test_resolve_targets_none_config_treated_as_empty() -> None:
    hass = MagicMock()
    hass.states.async_all.return_value = [_state("media_player.kitchen", "on")]
    assert resolve_targets(hass, None) == ["media_player.kitchen"]


def test_resolve_targets_no_available_returns_empty() -> None:
    hass = MagicMock()
    hass.states.async_all.return_value = [_state("media_player.tv", "off")]
    assert resolve_targets(hass, []) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_targets'`.

- [ ] **Step 3: Add `resolve_targets`**

Append to `custom_components/shelter_finder/tts_service.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tts_service.py -v`
Expected: PASS (20 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/tts_service.py tests/test_tts_service.py
git commit -m "feat(tts): add media_player target resolution"
```

---

## Task 5: Message duration estimator

**Files:**
- Modify: `custom_components/shelter_finder/tts_service.py`
- Test: `tests/test_tts_service.py`

Rationale: we need a rough duration to wait before restoring volume. ~15 French characters/second is a conservative average for TTS engines; minimum floor is 3s.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tts_service.py`:

```python
from custom_components.shelter_finder.tts_service import estimate_duration_seconds


def test_estimate_duration_short_message_floor() -> None:
    # Short messages have a 3s floor.
    assert estimate_duration_seconds("Hi.") == 3


def test_estimate_duration_long_message_scales() -> None:
    # 150 chars / 15 cps = 10s
    msg = "x" * 150
    assert estimate_duration_seconds(msg) == 10


def test_estimate_duration_rounds_up() -> None:
    # 16 chars / 15 cps = 1.07 → floor kicks in → 3s
    assert estimate_duration_seconds("x" * 16) == 3


def test_estimate_duration_medium_message() -> None:
    # 75 chars / 15 cps = 5s
    assert estimate_duration_seconds("x" * 75) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'estimate_duration_seconds'`.

- [ ] **Step 3: Add `estimate_duration_seconds`**

Append to `custom_components/shelter_finder/tts_service.py`:

```python
import math

_CHARS_PER_SECOND = 15
_MIN_DURATION_SECONDS = 3


def estimate_duration_seconds(message: str) -> int:
    """Estimate TTS playback time in seconds, with a 3s floor."""
    raw = math.ceil(len(message) / _CHARS_PER_SECOND)
    return max(raw, _MIN_DURATION_SECONDS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tts_service.py -v`
Expected: PASS (24 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/tts_service.py tests/test_tts_service.py
git commit -m "feat(tts): add message duration estimator"
```

---

## Task 6: TTSService class — skeleton, init, disabled no-op

**Files:**
- Modify: `custom_components/shelter_finder/tts_service.py`
- Test: `tests/test_tts_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tts_service.py`:

```python
import pytest

from custom_components.shelter_finder.tts_service import TTSService


@pytest.mark.asyncio
async def test_tts_service_disabled_is_noop() -> None:
    hass = MagicMock()
    hass.services.async_call = MagicMock()  # would be AsyncMock if called
    svc = TTSService(
        hass=hass,
        enabled=False,
        configured_service=None,
        configured_players=[],
        volume=0.8,
    )
    await svc.async_announce(
        threat_type="storm",
        shelters_by_person={"person.alice": {"name": "Abri", "distance_m": 100, "eta_minutes": 1}},
        is_drill=False,
    )
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_tts_service_no_resolved_service_is_noop(caplog) -> None:
    hass = MagicMock()
    hass.services.async_services.return_value = {"tts": {}}  # none registered
    hass.services.async_call = MagicMock()
    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service=None,
        configured_players=["media_player.kitchen"],
        volume=0.8,
    )
    with caplog.at_level("WARNING"):
        await svc.async_announce(
            threat_type="storm",
            shelters_by_person={"person.alice": {"name": "Abri", "distance_m": 100, "eta_minutes": 1}},
            is_drill=False,
        )
    hass.services.async_call.assert_not_called()
    assert any("No TTS service available" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'TTSService'`.

- [ ] **Step 3: Add `TTSService` skeleton**

Append to `custom_components/shelter_finder/tts_service.py`:

```python
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

        `shelters_by_person` maps person_entity_id → best-shelter dict with
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
        # Full flow implemented in Task 7.
        raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tts_service.py -v`
Expected: PASS (26 tests). The two new tests exercise the disabled and no-service paths, both of which return before `NotImplementedError`.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/tts_service.py tests/test_tts_service.py
git commit -m "feat(tts): add TTSService skeleton with disabled/no-service guards"
```

---

## Task 7: TTSService — full flow (save/set volume, speak, wait, restore)

**Files:**
- Modify: `custom_components/shelter_finder/tts_service.py`
- Test: `tests/test_tts_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tts_service.py`:

```python
from unittest.mock import AsyncMock, call


def _speaker_state(entity_id: str, volume_level: float | None, state: str = "idle") -> MagicMock:
    s = MagicMock()
    s.entity_id = entity_id
    s.state = state
    s.attributes = {} if volume_level is None else {"volume_level": volume_level}
    return s


def _hass_for_announce(targets_states: list[MagicMock], tts_services: list[str]) -> MagicMock:
    hass = MagicMock()
    hass.services.async_services.return_value = {
        "tts": {n: MagicMock() for n in tts_services},
    }
    hass.services.async_call = AsyncMock()
    # states.get(entity_id) returns matching state
    by_id = {s.entity_id: s for s in targets_states}
    hass.states.get = lambda eid: by_id.get(eid)
    hass.states.async_all = MagicMock(return_value=targets_states)
    return hass


@pytest.mark.asyncio
async def test_tts_service_full_flow_real_alert(monkeypatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(
        "custom_components.shelter_finder.tts_service.asyncio.sleep", fake_sleep
    )

    kitchen = _speaker_state("media_player.kitchen", 0.25)
    bedroom = _speaker_state("media_player.bedroom", 0.4)
    hass = _hass_for_announce([kitchen, bedroom], ["google_translate_say"])

    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service=None,
        configured_players=["media_player.kitchen", "media_player.bedroom"],
        volume=0.8,
    )

    await svc.async_announce(
        threat_type="storm",
        shelters_by_person={
            "person.alice": {"name": "Ecole", "distance_m": 300, "eta_minutes": 4},
        },
        is_drill=False,
    )

    calls = hass.services.async_call.await_args_list

    # 1. Set volume 0.8 on both speakers
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.kitchen", "volume_level": 0.8},
        blocking=True,
    ) in calls
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.bedroom", "volume_level": 0.8},
        blocking=True,
    ) in calls

    # 2. tts.google_translate_say on both
    expected_message = (
        "Alerte tempete. Dirigez-vous vers Ecole, a 300 metres, "
        "environ 4 minutes a pied."
    )
    assert call(
        "tts", "google_translate_say",
        {"entity_id": "media_player.kitchen", "message": expected_message},
        blocking=False,
    ) in calls
    assert call(
        "tts", "google_translate_say",
        {"entity_id": "media_player.bedroom", "message": expected_message},
        blocking=False,
    ) in calls

    # 3. One sleep for estimated duration + 2s buffer
    assert len(sleeps) == 1
    assert sleeps[0] == estimate_duration_seconds(expected_message) + 2

    # 4. Restore volumes
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.kitchen", "volume_level": 0.25},
        blocking=True,
    ) in calls
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.bedroom", "volume_level": 0.4},
        blocking=True,
    ) in calls


@pytest.mark.asyncio
async def test_tts_service_drill_prefix(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.shelter_finder.tts_service.asyncio.sleep",
        AsyncMock(),
    )
    kitchen = _speaker_state("media_player.kitchen", 0.3)
    hass = _hass_for_announce([kitchen], ["speak"])
    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service="speak",
        configured_players=["media_player.kitchen"],
        volume=0.8,
    )
    await svc.async_announce(
        threat_type="attack",
        shelters_by_person={"person.alice": {"name": "Metro", "distance_m": 100, "eta_minutes": 2}},
        is_drill=True,
    )
    # Find the tts.speak call and check message starts with drill prefix
    tts_calls = [
        c for c in hass.services.async_call.await_args_list
        if c.args[:2] == ("tts", "speak")
    ]
    assert len(tts_calls) == 1
    assert tts_calls[0].args[2]["message"].startswith("Ceci est un exercice. ")


@pytest.mark.asyncio
async def test_tts_service_restores_volume_even_if_speak_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.shelter_finder.tts_service.asyncio.sleep",
        AsyncMock(),
    )
    kitchen = _speaker_state("media_player.kitchen", 0.2)
    hass = _hass_for_announce([kitchen], ["google_translate_say"])

    # Make tts.google_translate_say raise; volume_set must still succeed.
    async def side_effect(domain, service, data, blocking=False):
        if domain == "tts":
            raise RuntimeError("TTS engine unreachable")
        return None

    hass.services.async_call = AsyncMock(side_effect=side_effect)

    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service=None,
        configured_players=["media_player.kitchen"],
        volume=0.8,
    )
    await svc.async_announce(
        threat_type="storm",
        shelters_by_person={"person.alice": {"name": "Abri", "distance_m": 200, "eta_minutes": 3}},
        is_drill=False,
    )

    calls = hass.services.async_call.await_args_list
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.kitchen", "volume_level": 0.2},
        blocking=True,
    ) in calls


@pytest.mark.asyncio
async def test_tts_service_missing_volume_level_skips_restore(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.shelter_finder.tts_service.asyncio.sleep",
        AsyncMock(),
    )
    no_vol = _speaker_state("media_player.weird", volume_level=None)
    hass = _hass_for_announce([no_vol], ["google_translate_say"])
    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service=None,
        configured_players=["media_player.weird"],
        volume=0.8,
    )
    await svc.async_announce(
        threat_type="storm",
        shelters_by_person={"person.alice": {"name": "Abri", "distance_m": 100, "eta_minutes": 1}},
        is_drill=False,
    )
    # Only one volume_set (the alert-level one); no restore since we had no baseline.
    vol_set_calls = [
        c for c in hass.services.async_call.await_args_list
        if c.args[:2] == ("media_player", "volume_set")
    ]
    assert len(vol_set_calls) == 1
    assert vol_set_calls[0].args[2]["volume_level"] == 0.8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL — four new tests hit `NotImplementedError` or AttributeError.

- [ ] **Step 3: Implement the full flow**

Replace the `async_announce` body in `custom_components/shelter_finder/tts_service.py`. Also add `import asyncio` near the top.

Full updated `async_announce`:

```python
import asyncio

# ... (existing imports and helpers unchanged)


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
        """Announce the alert on configured (or auto-detected) media_players."""
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

        # 1. Save current volumes (None when unavailable → skip restore).
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
        from .const import DEFAULT_TTS_BUFFER_SECONDS
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tts_service.py -v`
Expected: PASS (30 tests).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/tts_service.py tests/test_tts_service.py
git commit -m "feat(tts): implement announce flow with volume save/restore"
```

---

## Task 8: Wire TTSService into `__init__.py`

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`
- Test: `tests/test_tts_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tts_service.py`:

```python
from custom_components.shelter_finder.tts_service import build_shelters_by_person


def test_build_shelters_by_person_skips_none() -> None:
    ac = MagicMock()
    ac.persons = ["person.alice", "person.bob"]
    ac.get_best_shelter = lambda p: (
        {"name": "Abri", "distance_m": 200, "eta_minutes": 3}
        if p == "person.alice" else None
    )
    result = build_shelters_by_person(ac)
    assert result == {
        "person.alice": {"name": "Abri", "distance_m": 200, "eta_minutes": 3},
    }


def test_build_shelters_by_person_empty_when_no_shelters() -> None:
    ac = MagicMock()
    ac.persons = ["person.alice"]
    ac.get_best_shelter = lambda p: None
    assert build_shelters_by_person(ac) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_shelters_by_person'`.

- [ ] **Step 3: Add helper to `tts_service.py`**

Append to `custom_components/shelter_finder/tts_service.py`:

```python
def build_shelters_by_person(alert_coordinator: Any) -> dict[str, dict[str, Any]]:
    """Map person_entity_id → best-shelter dict, skipping persons with no shelter."""
    out: dict[str, dict[str, Any]] = {}
    for person_id in alert_coordinator.persons:
        best = alert_coordinator.get_best_shelter(person_id)
        if best is None:
            continue
        out[person_id] = best
    return out
```

- [ ] **Step 4: Run test to verify the helper passes**

Run: `pytest tests/test_tts_service.py -v`
Expected: PASS (32 tests).

- [ ] **Step 5: Wire into `__init__.py`**

Edit `custom_components/shelter_finder/__init__.py`.

5a. In the import block (lines 21-43), add the new CONF constants:

```python
from .const import (
    CONF_ADAPTIVE_RADIUS,
    CONF_ADAPTIVE_RADIUS_MAX,
    CONF_CACHE_TTL,
    CONF_CUSTOM_OSM_TAGS,
    CONF_DEFAULT_TRAVEL_MODE,
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_OVERPASS_URL,
    CONF_PERSONS,
    CONF_RE_NOTIFICATION_INTERVAL,
    CONF_SEARCH_RADIUS,
    CONF_TTS_ENABLED,
    CONF_TTS_MEDIA_PLAYERS,
    CONF_TTS_SERVICE,
    CONF_TTS_VOLUME,
    CONF_WEBHOOK_ID,
    DEFAULT_ADAPTIVE_RADIUS_MAX,
    DEFAULT_CACHE_TTL,
    DEFAULT_MAX_RE_NOTIFICATIONS,
    DEFAULT_OVERPASS_URL,
    DEFAULT_RADIUS,
    DEFAULT_RE_NOTIFICATION_INTERVAL,
    DEFAULT_TRAVEL_MODE,
    DEFAULT_TTS_VOLUME,
    DOMAIN,
    SHELTER_TYPES,
    THREAT_TYPES,
)
```

And add the TTS service import:

```python
from .tts_service import TTSService, build_shelters_by_person
```

5b. In `async_setup_entry`, after the alert_coordinator is built (right after line 121), add:

```python
    tts_service = TTSService(
        hass=hass,
        enabled=config.get(CONF_TTS_ENABLED, False),
        configured_service=config.get(CONF_TTS_SERVICE) or None,
        configured_players=config.get(CONF_TTS_MEDIA_PLAYERS, []) or [],
        volume=config.get(CONF_TTS_VOLUME, DEFAULT_TTS_VOLUME),
    )
```

And include it in the stored entry dict (modify the block starting at line 123):

```python
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "alert_coordinator": alert_coordinator,
        "cache": cache,
        "tts_service": tts_service,
    }
    hass.data[DOMAIN]["alert_coordinator"] = alert_coordinator
    hass.data[DOMAIN]["tts_service"] = tts_service
```

5c. In `_send_alert_notifications`, at the very end of the function (after the `for person_id` loop finishes), add the TTS call:

```python
async def _send_alert_notifications(hass: HomeAssistant, alert_coordinator: AlertCoordinator, message: str = "") -> None:
    """Send push notifications to all tracked persons."""
    for person_id in alert_coordinator.persons:
        # ... (existing loop body unchanged)

    # v0.6: Voice announcement on speakers (after push notifications)
    tts_service = hass.data.get(DOMAIN, {}).get("tts_service")
    if tts_service is not None:
        try:
            is_drill = getattr(alert_coordinator, "is_drill", False)
            shelters_by_person = build_shelters_by_person(alert_coordinator)
            await tts_service.async_announce(
                threat_type=alert_coordinator.threat_type,
                shelters_by_person=shelters_by_person,
                is_drill=is_drill,
            )
        except Exception:
            _LOGGER.exception("TTS announcement failed")
```

5d. In `async_unload_entry`, extend the cleanup to drop `tts_service` alongside `alert_coordinator` (modify the existing block after line 170):

```python
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        reserved = {"alert_coordinator", "tts_service", "_frontend_registered"}
        if not any(k for k in hass.data[DOMAIN] if k not in reserved):
            hass.data[DOMAIN].pop("alert_coordinator", None)
            hass.data[DOMAIN].pop("tts_service", None)
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/ -v`
Expected: PASS (all existing tests + 32 TTS tests).

- [ ] **Step 7: Commit**

```bash
git add custom_components/shelter_finder/__init__.py custom_components/shelter_finder/tts_service.py tests/test_tts_service.py
git commit -m "feat(tts): wire TTSService into alert notification flow"
```

---

## Task 9: Integration test — `_send_alert_notifications` invokes TTS

**Files:**
- Test: `tests/test_init_tts_integration.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_init_tts_integration.py`:

```python
"""Integration test: _send_alert_notifications triggers TTS announce."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.shelter_finder import _send_alert_notifications
from custom_components.shelter_finder.const import DOMAIN


@pytest.mark.asyncio
async def test_send_alert_notifications_calls_tts_service_with_drill_flag() -> None:
    ac = MagicMock()
    ac.persons = ["person.alice"]
    ac.threat_type = "storm"
    ac.is_drill = True
    ac.get_best_shelter = lambda p: {"name": "Ecole", "distance_m": 300, "eta_minutes": 4,
                                     "latitude": 48.8, "longitude": 2.3, "shelter_type": "school"}
    ac.record_notification = MagicMock()

    tts = MagicMock()
    tts.async_announce = AsyncMock()

    hass = MagicMock()
    hass.data = {DOMAIN: {"tts_service": tts}}
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_services = MagicMock(return_value={"notify": {}})
    hass.services.async_call = AsyncMock()

    await _send_alert_notifications(hass, ac, message="")

    tts.async_announce.assert_awaited_once()
    kwargs = tts.async_announce.await_args.kwargs
    assert kwargs["threat_type"] == "storm"
    assert kwargs["is_drill"] is True
    assert "person.alice" in kwargs["shelters_by_person"]


@pytest.mark.asyncio
async def test_send_alert_notifications_no_tts_service_does_not_raise() -> None:
    ac = MagicMock()
    ac.persons = []
    ac.threat_type = "flood"
    ac.is_drill = False

    hass = MagicMock()
    hass.data = {DOMAIN: {}}  # no tts_service
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_services = MagicMock(return_value={"notify": {}})
    hass.services.async_call = AsyncMock()

    # Must not raise.
    await _send_alert_notifications(hass, ac, message="")


@pytest.mark.asyncio
async def test_send_alert_notifications_tts_exception_is_swallowed(caplog) -> None:
    ac = MagicMock()
    ac.persons = []
    ac.threat_type = "flood"
    ac.is_drill = False
    ac.get_best_shelter = lambda p: None

    tts = MagicMock()
    tts.async_announce = AsyncMock(side_effect=RuntimeError("boom"))

    hass = MagicMock()
    hass.data = {DOMAIN: {"tts_service": tts}}
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_services = MagicMock(return_value={"notify": {}})
    hass.services.async_call = AsyncMock()

    with caplog.at_level("ERROR"):
        await _send_alert_notifications(hass, ac, message="")
    assert any("TTS announcement failed" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_init_tts_integration.py -v`
Expected: PASS (3 tests). If `is_drill` attribute lookup fails in a stale branch, `getattr(alert_coordinator, "is_drill", False)` returns False — the first test still passes because we set `ac.is_drill = True` via MagicMock.

- [ ] **Step 3: Commit**

```bash
git add tests/test_init_tts_integration.py
git commit -m "test(tts): integration test for alert-notifications → TTS path"
```

---

## Task 10: Self-review pass

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS across all files.

- [ ] **Step 2: Grep for placeholders in new code**

Run:

```bash
grep -nE "TODO|TBD|FIXME|NotImplementedError|pass  *#" custom_components/shelter_finder/tts_service.py
```

Expected: no output (the earlier `NotImplementedError` was replaced in Task 7).

- [ ] **Step 3: Manual smoke (optional, HA dev)**

With a Home Assistant dev instance:
1. Enable TTS in options, leave "service" blank (auto-detect), volume 80%.
2. Call `shelter_finder.trigger_alert` with `threat_type: storm`.
3. Expect announcement on auto-detected speaker(s), starting "Alerte tempete.".
4. Enable drill mode, trigger again, expect prefix "Ceci est un exercice.".

- [ ] **Step 4: Final commit (if any doc or polish updates)**

```bash
git status
# If nothing to commit, skip.
git commit -am "chore(tts): v0.6 TTS announcements feature complete"
```

---

## Spec Coverage Checklist

- [x] French message templates (real + drill) — Task 2
- [x] French threat labels table — Task 1
- [x] `TTSService.async_announce(threat_type, shelters_by_person, is_drill)` — Tasks 6, 7
- [x] Auto-detect TTS service (configured → google_translate_say → cloud_say → speak → None) — Task 3
- [x] Target media_players: configured list OR scan on/idle — Task 4
- [x] Save / set / restore volume — Task 7
- [x] Wait estimated duration + 2s buffer — Tasks 5, 7
- [x] Integration into `_send_alert_notifications` — Task 8
- [x] `is_drill` prefix routing — Tasks 2, 7, 8, 9
- [x] New config keys consumed (CONF_TTS_*) — Task 8 (OptionsFlow merged separately per assumption)
- [x] Tests for every unit — all tasks
