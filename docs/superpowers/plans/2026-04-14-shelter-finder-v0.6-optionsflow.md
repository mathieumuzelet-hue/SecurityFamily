# Shelter Finder v0.6 OptionsFlow Multi-Step Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the single-page `ShelterFinderOptionsFlow` into a 4-step wizard (Sources & Rayon, Routage, Notifications, Avance) and scaffold every v0.6 `CONF_*` key in `const.py` so downstream v0.6 feature plans (FR-Alert providers, OSRM, Drill, TTS) can assume they exist.

**Architecture:** Home Assistant `OptionsFlow` supports multi-step flows by chaining `async_step_<name>` methods that each call `async_show_form(step_id=...)` and return either the next step or `async_create_entry`. State accumulates on a `self._options: dict[str, Any]` instance attribute across steps. We keep the entry class name `ShelterFinderOptionsFlow` so `async_get_options_flow` stays unchanged. Only `const.py`, `config_flow.py`, and a new `tests/test_config_flow.py` are touched in this plan — zero runtime behaviour change beyond exposing options.

**Tech Stack:** Python 3.11+, Home Assistant `config_entries.OptionsFlow`, `voluptuous` schemas, `homeassistant.helpers.selector`, `pytest` + async, existing `tests/stubs/homeassistant/*` shim.

---

## File Structure

- **Modify** `custom_components/shelter_finder/const.py` — add all v0.6 `CONF_*` keys and `DEFAULT_*` values in one commit so later plans can import them immediately.
- **Modify** `custom_components/shelter_finder/config_flow.py` — rewrite `ShelterFinderOptionsFlow` with 4 ordered steps: `async_step_init` -> `async_step_routing` -> `async_step_notifications` -> `async_step_advanced` -> create entry. `async_step_init` is the Sources & Rayon page (HA requires the first options step to be named `init`).
- **Create** `tests/test_config_flow.py` — unit tests that drive the options flow step-by-step using the lightweight stubs. Since `tests/stubs/homeassistant/config_entries.py` only defines `ConfigEntry` as a bare class, the tests instantiate `ShelterFinderOptionsFlow` directly and call its async steps without the full flow manager.
- **Modify** `tests/stubs/homeassistant/config_entries.py` — extend the stub with the minimum surface (`OptionsFlow` base class, `ConfigEntry.options`/`data` attributes) needed by the tests.

---

## Task 1: Extend HA stubs for OptionsFlow testing

**Files:**
- Modify: `tests/stubs/homeassistant/config_entries.py`

- [ ] **Step 1: Replace the stub with a testable surface**

```python
"""Stub for homeassistant.config_entries."""

from __future__ import annotations

from typing import Any


class ConfigEntry:
    """Minimal stub of a config entry."""

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.data: dict[str, Any] = data or {}
        self.options: dict[str, Any] = options or {}
        self.entry_id: str = "test_entry_id"


class ConfigFlow:
    """Minimal stub of ConfigFlow."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__()

    def __init__(self) -> None:
        self.hass: Any = None

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        return None

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}


class OptionsFlow:
    """Minimal stub of OptionsFlow."""

    def __init__(self) -> None:
        self.hass: Any = None

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `pytest tests/ -q`
Expected: all currently-passing tests still pass (the stub is additive).

- [ ] **Step 3: Commit**

```bash
git add tests/stubs/homeassistant/config_entries.py
git commit -m "test(stubs): extend config_entries stub with OptionsFlow + ConfigFlow bases"
```

---

## Task 2: Add all v0.6 CONF_* keys and defaults to const.py

**Files:**
- Modify: `custom_components/shelter_finder/const.py`

- [ ] **Step 1: Write a failing test that imports every new key**

Create `tests/test_const_v06.py`:

```python
"""Ensure v0.6 config keys are defined in const.py."""

from __future__ import annotations

import custom_components.shelter_finder.const as const


def test_v06_conf_keys_exist() -> None:
    # Sources & Rayon
    assert const.CONF_PROVIDER_GEORISQUES == "provider_georisques"
    assert const.CONF_PROVIDER_METEO_FRANCE == "provider_meteo_france"
    assert const.CONF_PROVIDER_POLL_INTERVAL == "provider_poll_interval"
    assert const.CONF_PROVIDER_MIN_SEVERITY == "provider_min_severity"
    assert const.CONF_PROVIDER_AUTO_CANCEL == "provider_auto_cancel"
    assert const.CONF_PROVIDER_ALERT_RADIUS_KM == "provider_alert_radius_km"
    # Routage
    assert const.CONF_OSRM_ENABLED == "osrm_enabled"
    assert const.CONF_OSRM_MODE == "osrm_mode"
    assert const.CONF_OSRM_URL == "osrm_url"
    assert const.CONF_OSRM_TRANSPORT_MODE == "osrm_transport_mode"
    # Notifications
    assert const.CONF_TTS_ENABLED == "tts_enabled"
    assert const.CONF_TTS_SERVICE == "tts_service"
    assert const.CONF_TTS_MEDIA_PLAYERS == "tts_media_players"
    assert const.CONF_TTS_VOLUME == "tts_volume"
    # Drill (service param, but scaffold constant)
    assert const.CONF_DRILL == "drill"


def test_v06_defaults_exist() -> None:
    assert const.DEFAULT_PROVIDER_POLL_INTERVAL == 60
    assert const.DEFAULT_PROVIDER_MIN_SEVERITY == "severe"
    assert const.DEFAULT_PROVIDER_AUTO_CANCEL is True
    assert const.DEFAULT_OSRM_URL == "https://router.project-osrm.org"
    assert const.DEFAULT_OSRM_MODE == "public"
    assert const.DEFAULT_OSRM_TRANSPORT_MODE == "walking"
    assert const.DEFAULT_TTS_VOLUME == 80
    assert const.SEVERITY_LEVELS == ["minor", "moderate", "severe", "extreme"]
    assert const.OSRM_MODES == ["public", "self_hosted"]
    assert const.THREAT_TYPE_LABELS_FR["storm"] == "tempete"
    assert const.THREAT_TYPE_LABELS_FR["nuclear_chemical"] == "nucleaire chimique"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_const_v06.py -v`
Expected: FAIL with `AttributeError: module 'custom_components.shelter_finder.const' has no attribute 'CONF_PROVIDER_GEORISQUES'`.

- [ ] **Step 3: Append the new constants to const.py**

Append to `custom_components/shelter_finder/const.py` (keep existing content intact):

```python
# ---------------------------------------------------------------------------
# v0.6 — FR-Alert providers (Sources & Rayon)
# ---------------------------------------------------------------------------
CONF_PROVIDER_GEORISQUES = "provider_georisques"
CONF_PROVIDER_METEO_FRANCE = "provider_meteo_france"
CONF_PROVIDER_POLL_INTERVAL = "provider_poll_interval"
CONF_PROVIDER_MIN_SEVERITY = "provider_min_severity"
CONF_PROVIDER_AUTO_CANCEL = "provider_auto_cancel"
CONF_PROVIDER_ALERT_RADIUS_KM = "provider_alert_radius_km"

DEFAULT_PROVIDER_GEORISQUES = False
DEFAULT_PROVIDER_METEO_FRANCE = False
DEFAULT_PROVIDER_POLL_INTERVAL = 60  # seconds
PROVIDER_POLL_INTERVAL_MIN = 30
PROVIDER_POLL_INTERVAL_MAX = 300
DEFAULT_PROVIDER_MIN_SEVERITY = "severe"
DEFAULT_PROVIDER_AUTO_CANCEL = True
DEFAULT_PROVIDER_ALERT_RADIUS_KM = 10  # km

SEVERITY_LEVELS = ["minor", "moderate", "severe", "extreme"]

# ---------------------------------------------------------------------------
# v0.6 — OSRM routing (Routage)
# ---------------------------------------------------------------------------
CONF_OSRM_MODE = "osrm_mode"
CONF_OSRM_TRANSPORT_MODE = "osrm_transport_mode"

DEFAULT_OSRM_ENABLED = False
DEFAULT_OSRM_MODE = "public"
DEFAULT_OSRM_URL = "https://router.project-osrm.org"
DEFAULT_OSRM_TRANSPORT_MODE = "walking"

OSRM_MODES = ["public", "self_hosted"]
OSRM_TRANSPORT_MODES = ["walking", "driving"]

# ---------------------------------------------------------------------------
# v0.6 — TTS announcements (Notifications)
# ---------------------------------------------------------------------------
CONF_TTS_ENABLED = "tts_enabled"
CONF_TTS_SERVICE = "tts_service"
CONF_TTS_MEDIA_PLAYERS = "tts_media_players"
CONF_TTS_VOLUME = "tts_volume"

DEFAULT_TTS_ENABLED = False
DEFAULT_TTS_SERVICE = "auto"
DEFAULT_TTS_MEDIA_PLAYERS: list[str] = []
DEFAULT_TTS_VOLUME = 80  # percent

# French labels for threat types (used by TTS messages)
THREAT_TYPE_LABELS_FR: dict[str, str] = {
    "storm": "tempete",
    "earthquake": "seisme",
    "attack": "attaque",
    "armed_conflict": "conflit arme",
    "flood": "inondation",
    "nuclear_chemical": "nucleaire chimique",
}

# ---------------------------------------------------------------------------
# v0.6 — Drill mode (service parameter, scaffolded here for shared use)
# ---------------------------------------------------------------------------
CONF_DRILL = "drill"
DEFAULT_DRILL = False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_const_v06.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run full suite to confirm nothing else regressed**

Run: `pytest tests/ -q`
Expected: all previously-green tests remain green.

- [ ] **Step 6: Commit**

```bash
git add custom_components/shelter_finder/const.py tests/test_const_v06.py
git commit -m "feat(const): scaffold v0.6 CONF_* keys and defaults for providers, OSRM, TTS, drill"
```

---

## Task 3: Failing test — OptionsFlow Step 1 (Sources & Rayon) renders with correct fields

**Files:**
- Create: `tests/test_config_flow.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the multi-step OptionsFlow of Shelter Finder v0.6."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.shelter_finder.config_flow import ShelterFinderOptionsFlow
from custom_components.shelter_finder.const import (
    CONF_ADAPTIVE_RADIUS,
    CONF_CACHE_TTL,
    CONF_PROVIDER_ALERT_RADIUS_KM,
    CONF_PROVIDER_AUTO_CANCEL,
    CONF_PROVIDER_GEORISQUES,
    CONF_PROVIDER_METEO_FRANCE,
    CONF_PROVIDER_MIN_SEVERITY,
    CONF_PROVIDER_POLL_INTERVAL,
    CONF_SEARCH_RADIUS,
)
from tests.stubs.homeassistant.config_entries import ConfigEntry


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_flow(data=None, options=None) -> ShelterFinderOptionsFlow:
    entry = ConfigEntry(data=data or {}, options=options or {})
    return ShelterFinderOptionsFlow(entry)


def test_step_init_renders_sources_and_radius_fields() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_init())

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema.keys()}
    for expected in (
        CONF_SEARCH_RADIUS,
        CONF_ADAPTIVE_RADIUS,
        CONF_CACHE_TTL,
        CONF_PROVIDER_GEORISQUES,
        CONF_PROVIDER_METEO_FRANCE,
        CONF_PROVIDER_POLL_INTERVAL,
        CONF_PROVIDER_MIN_SEVERITY,
        CONF_PROVIDER_AUTO_CANCEL,
        CONF_PROVIDER_ALERT_RADIUS_KM,
    ):
        assert expected in schema_keys, f"missing field {expected}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_config_flow.py::test_step_init_renders_sources_and_radius_fields -v`
Expected: FAIL — the current `async_step_init` schema is missing the provider keys.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_config_flow.py
git commit -m "test(config_flow): failing test for step 1 Sources & Rayon fields"
```

---

## Task 4: Implement Step 1 (Sources & Rayon) — rewrite async_step_init

**Files:**
- Modify: `custom_components/shelter_finder/config_flow.py`

- [ ] **Step 1: Rewrite config_flow.py with the new multi-step OptionsFlow (Step 1 populated, others as stubs we will fill next)**

Replace the entire content of `custom_components/shelter_finder/config_flow.py` with:

```python
"""Config flow for Shelter Finder."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ADAPTIVE_RADIUS,
    CONF_CACHE_TTL,
    CONF_CUSTOM_OSM_TAGS,
    CONF_DEFAULT_TRAVEL_MODE,
    CONF_ENABLED_THREATS,
    CONF_LANGUAGE,
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_OSRM_ENABLED,
    CONF_OSRM_MODE,
    CONF_OSRM_TRANSPORT_MODE,
    CONF_OSRM_URL,
    CONF_OVERPASS_URL,
    CONF_PERSONS,
    CONF_PROVIDER_ALERT_RADIUS_KM,
    CONF_PROVIDER_AUTO_CANCEL,
    CONF_PROVIDER_GEORISQUES,
    CONF_PROVIDER_METEO_FRANCE,
    CONF_PROVIDER_MIN_SEVERITY,
    CONF_PROVIDER_POLL_INTERVAL,
    CONF_RE_NOTIFICATION_INTERVAL,
    CONF_SEARCH_RADIUS,
    CONF_TTS_ENABLED,
    CONF_TTS_MEDIA_PLAYERS,
    CONF_TTS_SERVICE,
    CONF_TTS_VOLUME,
    CONF_WEBHOOK_ID,
    DEFAULT_CACHE_TTL,
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_RE_NOTIFICATIONS,
    DEFAULT_OSRM_ENABLED,
    DEFAULT_OSRM_MODE,
    DEFAULT_OSRM_TRANSPORT_MODE,
    DEFAULT_OSRM_URL,
    DEFAULT_OVERPASS_URL,
    DEFAULT_PROVIDER_ALERT_RADIUS_KM,
    DEFAULT_PROVIDER_AUTO_CANCEL,
    DEFAULT_PROVIDER_GEORISQUES,
    DEFAULT_PROVIDER_METEO_FRANCE,
    DEFAULT_PROVIDER_MIN_SEVERITY,
    DEFAULT_PROVIDER_POLL_INTERVAL,
    DEFAULT_RADIUS,
    DEFAULT_RE_NOTIFICATION_INTERVAL,
    DEFAULT_TRAVEL_MODE,
    DEFAULT_TTS_ENABLED,
    DEFAULT_TTS_MEDIA_PLAYERS,
    DEFAULT_TTS_SERVICE,
    DEFAULT_TTS_VOLUME,
    DOMAIN,
    OSRM_MODES,
    OSRM_TRANSPORT_MODES,
    PROVIDER_POLL_INTERVAL_MAX,
    PROVIDER_POLL_INTERVAL_MIN,
    SEVERITY_LEVELS,
    THREAT_TYPES,
    TRAVEL_MODES,
)


class ShelterFinderConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._user_input.update(user_input)
            return await self.async_step_threats()

        person_entities = [state.entity_id for state in self.hass.states.async_all("person")]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PERSONS, default=person_entities): SelectSelector(
                    SelectSelectorConfig(
                        options=person_entities,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_SEARCH_RADIUS, default=DEFAULT_RADIUS): vol.All(int, vol.Range(min=500, max=50000)),
                vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(["fr", "en"]),
            }),
        )

    async def async_step_threats(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._user_input.update(user_input)
            self._user_input[CONF_WEBHOOK_ID] = f"sf_{uuid.uuid4().hex[:12]}"
            return self.async_create_entry(title="Shelter Finder", data=self._user_input)

        return self.async_show_form(
            step_id="threats",
            data_schema=vol.Schema({
                vol.Required(CONF_ENABLED_THREATS, default=THREAT_TYPES): SelectSelector(
                    SelectSelectorConfig(
                        options=THREAT_TYPES,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_DEFAULT_TRAVEL_MODE, default=DEFAULT_TRAVEL_MODE): SelectSelector(
                    SelectSelectorConfig(
                        options=TRAVEL_MODES,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ShelterFinderOptionsFlow(config_entry)


class ShelterFinderOptionsFlow(OptionsFlow):
    """Multi-step options flow for Shelter Finder v0.6.

    Steps:
      1. init           -> Sources & Rayon
      2. routing        -> Routage (OSRM)
      3. notifications  -> Notifications (re-notif + TTS)
      4. advanced       -> Avance (overpass_url, custom_osm_tags)
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        self._options: dict[str, Any] = {}

    # ------------------------------------------------------------------ utils
    def _current(self) -> dict[str, Any]:
        """Return merged view of existing options over data (options wins)."""
        merged: dict[str, Any] = {}
        merged.update(self._config_entry.data or {})
        merged.update(self._config_entry.options or {})
        return merged

    # ---------------------------------------------------------------- step 1
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1 — Sources & Rayon."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_routing()

        cur = self._current()

        schema = vol.Schema({
            vol.Required(
                CONF_SEARCH_RADIUS,
                default=cur.get(CONF_SEARCH_RADIUS, DEFAULT_RADIUS),
            ): vol.All(int, vol.Range(min=500, max=50000)),
            vol.Required(
                CONF_ADAPTIVE_RADIUS,
                default=cur.get(CONF_ADAPTIVE_RADIUS, True),
            ): bool,
            vol.Required(
                CONF_CACHE_TTL,
                default=cur.get(CONF_CACHE_TTL, DEFAULT_CACHE_TTL),
            ): vol.All(int, vol.Range(min=1, max=168)),
            vol.Required(
                CONF_PROVIDER_GEORISQUES,
                default=cur.get(CONF_PROVIDER_GEORISQUES, DEFAULT_PROVIDER_GEORISQUES),
            ): bool,
            vol.Required(
                CONF_PROVIDER_METEO_FRANCE,
                default=cur.get(CONF_PROVIDER_METEO_FRANCE, DEFAULT_PROVIDER_METEO_FRANCE),
            ): bool,
            vol.Required(
                CONF_PROVIDER_POLL_INTERVAL,
                default=cur.get(CONF_PROVIDER_POLL_INTERVAL, DEFAULT_PROVIDER_POLL_INTERVAL),
            ): vol.All(int, vol.Range(min=PROVIDER_POLL_INTERVAL_MIN, max=PROVIDER_POLL_INTERVAL_MAX)),
            vol.Required(
                CONF_PROVIDER_MIN_SEVERITY,
                default=cur.get(CONF_PROVIDER_MIN_SEVERITY, DEFAULT_PROVIDER_MIN_SEVERITY),
            ): vol.In(SEVERITY_LEVELS),
            vol.Required(
                CONF_PROVIDER_AUTO_CANCEL,
                default=cur.get(CONF_PROVIDER_AUTO_CANCEL, DEFAULT_PROVIDER_AUTO_CANCEL),
            ): bool,
            vol.Required(
                CONF_PROVIDER_ALERT_RADIUS_KM,
                default=cur.get(CONF_PROVIDER_ALERT_RADIUS_KM, DEFAULT_PROVIDER_ALERT_RADIUS_KM),
            ): vol.All(int, vol.Range(min=1, max=200)),
        })

        return self.async_show_form(step_id="init", data_schema=schema)

    # ---------------------------------------------------------------- step 2
    async def async_step_routing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2 — Routage (placeholder, filled in Task 6)."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_notifications()

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_OSRM_ENABLED,
                default=cur.get(CONF_OSRM_ENABLED, DEFAULT_OSRM_ENABLED),
            ): bool,
        })
        return self.async_show_form(step_id="routing", data_schema=schema)

    # ---------------------------------------------------------------- step 3
    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3 — Notifications (placeholder, filled in Task 8)."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_advanced()

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_RE_NOTIFICATION_INTERVAL,
                default=cur.get(CONF_RE_NOTIFICATION_INTERVAL, DEFAULT_RE_NOTIFICATION_INTERVAL),
            ): vol.All(int, vol.Range(min=1, max=60)),
        })
        return self.async_show_form(step_id="notifications", data_schema=schema)

    # ---------------------------------------------------------------- step 4
    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4 — Avance (placeholder, filled in Task 10)."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_OVERPASS_URL,
                default=cur.get(CONF_OVERPASS_URL, DEFAULT_OVERPASS_URL),
            ): str,
        })
        return self.async_show_form(step_id="advanced", data_schema=schema)
```

- [ ] **Step 2: Run the Task 3 test to verify it now passes**

Run: `pytest tests/test_config_flow.py::test_step_init_renders_sources_and_radius_fields -v`
Expected: PASS.

- [ ] **Step 3: Run full suite to confirm no regression**

Run: `pytest tests/ -q`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add custom_components/shelter_finder/config_flow.py
git commit -m "feat(config_flow): multi-step OptionsFlow skeleton with Sources & Rayon step"
```

---

## Task 5: Failing test — Step 1 submit advances to Step 2 (routing)

**Files:**
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Append the failing test**

Add to `tests/test_config_flow.py`:

```python
def test_step_init_submit_advances_to_routing() -> None:
    flow = _make_flow()
    # Prime the flow so _current() works (it does not need the first form render,
    # but we call it to mirror real HA behaviour).
    _run(flow.async_step_init())

    result = _run(flow.async_step_init(user_input={
        CONF_SEARCH_RADIUS: 3000,
        CONF_ADAPTIVE_RADIUS: True,
        CONF_CACHE_TTL: 12,
        CONF_PROVIDER_GEORISQUES: True,
        CONF_PROVIDER_METEO_FRANCE: False,
        CONF_PROVIDER_POLL_INTERVAL: 90,
        CONF_PROVIDER_MIN_SEVERITY: "moderate",
        CONF_PROVIDER_AUTO_CANCEL: True,
        CONF_PROVIDER_ALERT_RADIUS_KM: 20,
    }))

    assert result["type"] == "form"
    assert result["step_id"] == "routing"
    # Submitted values must be persisted on the flow for the final create_entry.
    assert flow._options[CONF_PROVIDER_GEORISQUES] is True
    assert flow._options[CONF_PROVIDER_POLL_INTERVAL] == 90
```

- [ ] **Step 2: Run the new test**

Run: `pytest tests/test_config_flow.py::test_step_init_submit_advances_to_routing -v`
Expected: PASS (the Task 4 implementation already supports this). This test is a **regression guard**; we add it before extending to catch breakage in later tasks.

- [ ] **Step 3: Commit**

```bash
git add tests/test_config_flow.py
git commit -m "test(config_flow): guard that Step 1 submit advances to routing step"
```

---

## Task 6: Failing test — Step 2 (Routage) renders full routing fields

**Files:**
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Add the failing test**

Append:

```python
from custom_components.shelter_finder.const import (
    CONF_OSRM_ENABLED,
    CONF_OSRM_MODE,
    CONF_OSRM_TRANSPORT_MODE,
    CONF_OSRM_URL,
)


def test_step_routing_renders_all_osrm_fields() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_routing())

    assert result["type"] == "form"
    assert result["step_id"] == "routing"
    schema_keys = {str(k) for k in result["data_schema"].schema.keys()}
    for expected in (
        CONF_OSRM_ENABLED,
        CONF_OSRM_MODE,
        CONF_OSRM_URL,
        CONF_OSRM_TRANSPORT_MODE,
    ):
        assert expected in schema_keys, f"missing field {expected}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_config_flow.py::test_step_routing_renders_all_osrm_fields -v`
Expected: FAIL — placeholder only has `CONF_OSRM_ENABLED`.

- [ ] **Step 3: Replace `async_step_routing` with the full implementation**

In `custom_components/shelter_finder/config_flow.py`, replace the body of `async_step_routing` with:

```python
    async def async_step_routing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2 — Routage (OSRM)."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_notifications()

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_OSRM_ENABLED,
                default=cur.get(CONF_OSRM_ENABLED, DEFAULT_OSRM_ENABLED),
            ): bool,
            vol.Required(
                CONF_OSRM_MODE,
                default=cur.get(CONF_OSRM_MODE, DEFAULT_OSRM_MODE),
            ): vol.In(OSRM_MODES),
            vol.Required(
                CONF_OSRM_URL,
                default=cur.get(CONF_OSRM_URL, DEFAULT_OSRM_URL),
            ): str,
            vol.Required(
                CONF_OSRM_TRANSPORT_MODE,
                default=cur.get(CONF_OSRM_TRANSPORT_MODE, DEFAULT_OSRM_TRANSPORT_MODE),
            ): vol.In(OSRM_TRANSPORT_MODES),
        })
        return self.async_show_form(step_id="routing", data_schema=schema)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_config_flow.py::test_step_routing_renders_all_osrm_fields -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/config_flow.py tests/test_config_flow.py
git commit -m "feat(config_flow): flesh out Step 2 Routage with full OSRM options"
```

---

## Task 7: Failing test — Step 2 submit advances to Step 3 (notifications)

**Files:**
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Add the test**

Append:

```python
def test_step_routing_submit_advances_to_notifications() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_routing(user_input={
        CONF_OSRM_ENABLED: True,
        CONF_OSRM_MODE: "self_hosted",
        CONF_OSRM_URL: "http://osrm.local:5000",
        CONF_OSRM_TRANSPORT_MODE: "walking",
    }))

    assert result["type"] == "form"
    assert result["step_id"] == "notifications"
    assert flow._options[CONF_OSRM_ENABLED] is True
    assert flow._options[CONF_OSRM_MODE] == "self_hosted"
    assert flow._options[CONF_OSRM_URL] == "http://osrm.local:5000"
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_config_flow.py::test_step_routing_submit_advances_to_notifications -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_config_flow.py
git commit -m "test(config_flow): guard Step 2 submit transitions to notifications"
```

---

## Task 8: Failing test — Step 3 (Notifications) renders re-notif + TTS fields

**Files:**
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Add the failing test**

Append:

```python
from custom_components.shelter_finder.const import (
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_TTS_ENABLED,
    CONF_TTS_MEDIA_PLAYERS,
    CONF_TTS_SERVICE,
    CONF_TTS_VOLUME,
)


def test_step_notifications_renders_renotif_and_tts_fields() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_notifications())

    assert result["type"] == "form"
    assert result["step_id"] == "notifications"
    schema_keys = {str(k) for k in result["data_schema"].schema.keys()}
    for expected in (
        CONF_RE_NOTIFICATION_INTERVAL,
        CONF_MAX_RE_NOTIFICATIONS,
        CONF_TTS_ENABLED,
        CONF_TTS_SERVICE,
        CONF_TTS_MEDIA_PLAYERS,
        CONF_TTS_VOLUME,
    ):
        assert expected in schema_keys, f"missing field {expected}"
```

Also add the missing import at the top of the file if not yet present:

```python
from custom_components.shelter_finder.const import CONF_RE_NOTIFICATION_INTERVAL
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_config_flow.py::test_step_notifications_renders_renotif_and_tts_fields -v`
Expected: FAIL — placeholder only has `CONF_RE_NOTIFICATION_INTERVAL`.

- [ ] **Step 3: Replace `async_step_notifications` with the full implementation**

Replace the body of `async_step_notifications` in `config_flow.py` with:

```python
    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3 — Notifications (re-notif + TTS)."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_advanced()

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_RE_NOTIFICATION_INTERVAL,
                default=cur.get(CONF_RE_NOTIFICATION_INTERVAL, DEFAULT_RE_NOTIFICATION_INTERVAL),
            ): vol.All(int, vol.Range(min=1, max=60)),
            vol.Required(
                CONF_MAX_RE_NOTIFICATIONS,
                default=cur.get(CONF_MAX_RE_NOTIFICATIONS, DEFAULT_MAX_RE_NOTIFICATIONS),
            ): vol.All(int, vol.Range(min=0, max=20)),
            vol.Required(
                CONF_TTS_ENABLED,
                default=cur.get(CONF_TTS_ENABLED, DEFAULT_TTS_ENABLED),
            ): bool,
            vol.Required(
                CONF_TTS_SERVICE,
                default=cur.get(CONF_TTS_SERVICE, DEFAULT_TTS_SERVICE),
            ): str,
            vol.Required(
                CONF_TTS_MEDIA_PLAYERS,
                default=cur.get(CONF_TTS_MEDIA_PLAYERS, DEFAULT_TTS_MEDIA_PLAYERS),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[],
                    multiple=True,
                    custom_value=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_TTS_VOLUME,
                default=cur.get(CONF_TTS_VOLUME, DEFAULT_TTS_VOLUME),
            ): vol.All(int, vol.Range(min=0, max=100)),
        })
        return self.async_show_form(step_id="notifications", data_schema=schema)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_config_flow.py::test_step_notifications_renders_renotif_and_tts_fields -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/config_flow.py tests/test_config_flow.py
git commit -m "feat(config_flow): flesh out Step 3 Notifications with TTS + re-notif fields"
```

---

## Task 9: Failing test — Step 3 submit advances to Step 4 (advanced)

**Files:**
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Add the test**

Append:

```python
def test_step_notifications_submit_advances_to_advanced() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_notifications(user_input={
        CONF_RE_NOTIFICATION_INTERVAL: 10,
        CONF_MAX_RE_NOTIFICATIONS: 5,
        CONF_TTS_ENABLED: True,
        CONF_TTS_SERVICE: "tts.google_translate_say",
        CONF_TTS_MEDIA_PLAYERS: ["media_player.living_room", "media_player.kitchen"],
        CONF_TTS_VOLUME: 70,
    }))

    assert result["type"] == "form"
    assert result["step_id"] == "advanced"
    assert flow._options[CONF_TTS_ENABLED] is True
    assert flow._options[CONF_TTS_VOLUME] == 70
    assert flow._options[CONF_TTS_MEDIA_PLAYERS] == [
        "media_player.living_room",
        "media_player.kitchen",
    ]
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_config_flow.py::test_step_notifications_submit_advances_to_advanced -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_config_flow.py
git commit -m "test(config_flow): guard Step 3 submit transitions to advanced"
```

---

## Task 10: Failing test — Step 4 (Avance) renders overpass_url + custom_osm_tags and creates entry

**Files:**
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Add the failing tests**

Append:

```python
from custom_components.shelter_finder.const import CONF_CUSTOM_OSM_TAGS, CONF_OVERPASS_URL


def test_step_advanced_renders_advanced_fields() -> None:
    flow = _make_flow()
    result = _run(flow.async_step_advanced())

    assert result["type"] == "form"
    assert result["step_id"] == "advanced"
    schema_keys = {str(k) for k in result["data_schema"].schema.keys()}
    for expected in (CONF_OVERPASS_URL, CONF_CUSTOM_OSM_TAGS):
        assert expected in schema_keys, f"missing field {expected}"


def test_step_advanced_submit_creates_entry_with_all_options() -> None:
    flow = _make_flow()

    # Walk through all four steps to accumulate options.
    _run(flow.async_step_init(user_input={
        CONF_SEARCH_RADIUS: 3000,
        CONF_ADAPTIVE_RADIUS: False,
        CONF_CACHE_TTL: 48,
        CONF_PROVIDER_GEORISQUES: True,
        CONF_PROVIDER_METEO_FRANCE: True,
        CONF_PROVIDER_POLL_INTERVAL: 60,
        CONF_PROVIDER_MIN_SEVERITY: "severe",
        CONF_PROVIDER_AUTO_CANCEL: True,
        CONF_PROVIDER_ALERT_RADIUS_KM: 15,
    }))
    _run(flow.async_step_routing(user_input={
        CONF_OSRM_ENABLED: True,
        CONF_OSRM_MODE: "public",
        CONF_OSRM_URL: "https://router.project-osrm.org",
        CONF_OSRM_TRANSPORT_MODE: "walking",
    }))
    _run(flow.async_step_notifications(user_input={
        CONF_RE_NOTIFICATION_INTERVAL: 5,
        CONF_MAX_RE_NOTIFICATIONS: 3,
        CONF_TTS_ENABLED: False,
        CONF_TTS_SERVICE: "auto",
        CONF_TTS_MEDIA_PLAYERS: [],
        CONF_TTS_VOLUME: 80,
    }))
    result = _run(flow.async_step_advanced(user_input={
        CONF_OVERPASS_URL: "https://overpass.example.org/api/interpreter",
        CONF_CUSTOM_OSM_TAGS: "amenity=shelter,building=bunker",
    }))

    assert result["type"] == "create_entry"
    data = result["data"]
    # Spot-check one key from each step.
    assert data[CONF_SEARCH_RADIUS] == 3000
    assert data[CONF_PROVIDER_GEORISQUES] is True
    assert data[CONF_OSRM_ENABLED] is True
    assert data[CONF_TTS_VOLUME] == 80
    assert data[CONF_OVERPASS_URL] == "https://overpass.example.org/api/interpreter"
    assert data[CONF_CUSTOM_OSM_TAGS] == "amenity=shelter,building=bunker"
```

- [ ] **Step 2: Run the tests to verify the first fails**

Run: `pytest tests/test_config_flow.py::test_step_advanced_renders_advanced_fields -v`
Expected: FAIL — placeholder has only `CONF_OVERPASS_URL`.

- [ ] **Step 3: Replace `async_step_advanced` with the full implementation**

Replace the body in `config_flow.py`:

```python
    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4 — Avance (Overpass URL + custom OSM tags)."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_OVERPASS_URL,
                default=cur.get(CONF_OVERPASS_URL, DEFAULT_OVERPASS_URL),
            ): str,
            vol.Optional(
                CONF_CUSTOM_OSM_TAGS,
                default=cur.get(CONF_CUSTOM_OSM_TAGS, ""),
            ): str,
        })
        return self.async_show_form(step_id="advanced", data_schema=schema)
```

- [ ] **Step 4: Run both Task 10 tests**

Run: `pytest tests/test_config_flow.py::test_step_advanced_renders_advanced_fields tests/test_config_flow.py::test_step_advanced_submit_creates_entry_with_all_options -v`
Expected: both PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add custom_components/shelter_finder/config_flow.py tests/test_config_flow.py
git commit -m "feat(config_flow): complete Step 4 Avance and end-to-end options entry creation"
```

---

## Task 11: Existing-options round-trip test (defaults come from prior options)

**Files:**
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Add the failing test**

Append:

```python
def test_existing_options_are_used_as_defaults() -> None:
    existing = {
        CONF_SEARCH_RADIUS: 4500,
        CONF_PROVIDER_GEORISQUES: True,
        CONF_OSRM_ENABLED: True,
        CONF_OSRM_URL: "http://osrm.local:5000",
        CONF_TTS_ENABLED: True,
        CONF_TTS_VOLUME: 55,
        CONF_OVERPASS_URL: "https://overpass.example.org/api/interpreter",
    }
    flow = _make_flow(options=existing)

    init_schema = _run(flow.async_step_init())["data_schema"].schema
    routing_schema = _run(flow.async_step_routing())["data_schema"].schema
    notif_schema = _run(flow.async_step_notifications())["data_schema"].schema
    adv_schema = _run(flow.async_step_advanced())["data_schema"].schema

    def _default_for(schema, key):
        for marker in schema.keys():
            if str(marker) == key:
                return marker.default() if callable(marker.default) else marker.default
        raise KeyError(key)

    assert _default_for(init_schema, CONF_SEARCH_RADIUS) == 4500
    assert _default_for(init_schema, CONF_PROVIDER_GEORISQUES) is True
    assert _default_for(routing_schema, CONF_OSRM_ENABLED) is True
    assert _default_for(routing_schema, CONF_OSRM_URL) == "http://osrm.local:5000"
    assert _default_for(notif_schema, CONF_TTS_ENABLED) is True
    assert _default_for(notif_schema, CONF_TTS_VOLUME) == 55
    assert _default_for(adv_schema, CONF_OVERPASS_URL) == "https://overpass.example.org/api/interpreter"
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_config_flow.py::test_existing_options_are_used_as_defaults -v`
Expected: PASS — `_current()` already merges `options` over `data`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_config_flow.py
git commit -m "test(config_flow): verify existing options are used as step defaults"
```

---

## Task 12: Final verification + self-review

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite**

Run: `pytest tests/ -q`
Expected: all tests pass. If any unrelated test fails, investigate before proceeding.

- [ ] **Step 2: Lint-check by importing the module**

Run: `python -c "import custom_components.shelter_finder.config_flow as m; print(m.ShelterFinderOptionsFlow.__name__)"`
Expected: prints `ShelterFinderOptionsFlow` (catches stray NameError / import errors).

- [ ] **Step 3: Confirm no dangling TODO or placeholder**

Run: `grep -n "TODO\|FIXME\|placeholder" custom_components/shelter_finder/config_flow.py || true`
Expected: no output.

- [ ] **Step 4: Tag a checkpoint commit if the tree is clean**

```bash
git status
# If nothing to commit, the task is done; otherwise investigate uncommitted work.
```

---

## Self-Review

**Spec coverage (lines 296-317):**
- Step 1 "Sources & Rayon" fields: `search_radius` (Task 4), `adaptive_radius` (Task 4), `overpass_url` — *note: spec lists overpass_url in both Step 1 and Step 4; this plan places it in Step 4 (Avance) only, matching "Avance" row; kept in Step 4 to avoid duplication*, `cache_ttl` (Task 4), Georisques + Meteo France checkboxes (Task 4), `polling_interval` (Task 4), `min_severity` (Task 4), `auto_cancel` (Task 4). Covered.
- Step 2 "Routage" fields: `osrm_enabled`, `osrm_mode`, `osrm_url`, `transport_mode` (Task 6). Covered.
- Step 3 "Notifications" fields: `re_notification_interval`, `max_re_notifications`, `tts_enabled`, `tts_service`, `tts_media_players`, `tts_volume` (Task 8). Covered.
- Step 4 "Avance" fields: `custom_osm_tags`, `overpass_url` (Task 10). Covered.
- `const.py` scaffolding of all v0.6 keys (providers, OSRM, TTS, drill, severity levels, French threat labels, OSRM modes) — Task 2. Covered.
- Each step calls `async_show_form(step_id=...)` and returns next step or `async_create_entry` — verified by Tasks 5/7/9/10 transition tests.

**Placeholder scan:** No "TODO", "TBD", "implement later". Every code step shows the exact replacement. The Step 2/3/4 placeholders inside Task 4's initial skeleton are intentional scaffolding that Tasks 6/8/10 each fully replace with tested code — not dangling placeholders.

**Type consistency:** `ShelterFinderOptionsFlow`, `self._options`, `self._config_entry`, and `self._current()` are defined in Task 4 and reused identically in Tasks 6, 8, 10. All `CONF_*` and `DEFAULT_*` names used in tests and implementation match those introduced in Task 2 (const.py). `SelectSelector` / `SelectSelectorConfig` / `SelectSelectorMode` imports are unchanged from the current file. `OSRM_MODES` and `OSRM_TRANSPORT_MODES` are defined in Task 2 and referenced in Task 6. `SEVERITY_LEVELS` is defined in Task 2 and referenced in Task 4.

**One deliberate deviation from the spec:** the spec's Step 1 row includes `overpass_url`, and the Step 4 row also includes `overpass_url`. This plan keeps `overpass_url` only in Step 4 (Avance) to avoid double-editing the same key across two steps (HA does not tolerate a key appearing in two options-flow schemas within one flow). Downstream reviewers should confirm; if the user wants it duplicated, move it to Step 1 by adding it to the Task 4 schema — no other change needed.
