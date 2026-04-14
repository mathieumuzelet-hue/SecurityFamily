# Shelter Finder v0.6 — Drill Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "drill" mode to the existing alert pipeline so users can practice evacuation scenarios with a visually distinct (yellow) banner, a lower-priority notification prefixed with `[EXERCICE]`, and a `drill=true` flag on `binary_sensor.alert`, without any new config entries.

**Architecture:** The drill state is carried as a single boolean `_is_drill` on `AlertCoordinator`, set by `trigger(..., drill=True)`. All downstream surfaces (binary sensor attribute, notification builder, Lovelace banner, third button entity) branch on that flag. The OptionsFlow plan (already merged) is untouched — drill is strictly a service/call-site parameter.

**Tech Stack:** Python 3.12 async, pytest + pytest-asyncio, voluptuous service schema, Home Assistant custom component APIs, vanilla JS (no Lit) for the Lovelace card.

---

## File Structure

- Modify: `custom_components/shelter_finder/alert_coordinator.py` — add `drill` param to `trigger()`, `_is_drill` state, `is_drill` property, reset on `cancel()`.
- Modify: `custom_components/shelter_finder/binary_sensor.py` — add `drill` key to `extra_state_attributes`.
- Modify: `custom_components/shelter_finder/__init__.py` — add `drill` to `trigger_alert` service schema; pass through to coordinator; branch title/priority in `_send_alert_notifications`.
- Modify: `custom_components/shelter_finder/button.py` — add `ShelterDrillButton`.
- Modify: `custom_components/shelter_finder/www/shelter-map-card.js` — banner reads `drill` attr, switches color/text.
- Modify: `tests/test_alert_coordinator.py` — drill flag tests.
- Modify: `tests/test_button.py` — drill button tests.
- Create: `tests/test_drill_notifications.py` — notification title/priority branching tests.

---

## Task 1: AlertCoordinator drill flag

**Files:**
- Modify: `custom_components/shelter_finder/alert_coordinator.py`
- Test: `tests/test_alert_coordinator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_alert_coordinator.py`:

```python
def test_trigger_default_is_not_drill(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual")
    assert alert_coord.is_drill is False

def test_trigger_with_drill_true(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual", drill=True)
    assert alert_coord.is_active is True
    assert alert_coord.is_drill is True
    assert alert_coord.threat_type == "storm"

def test_cancel_clears_drill_flag(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual", drill=True)
    alert_coord.cancel()
    assert alert_coord.is_drill is False

def test_retrigger_real_after_drill_resets_flag(alert_coord: AlertCoordinator) -> None:
    alert_coord.trigger("storm", triggered_by="manual", drill=True)
    alert_coord.cancel()
    alert_coord.trigger("flood", triggered_by="manual")
    assert alert_coord.is_drill is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_alert_coordinator.py -v -k "drill"`
Expected: 4 failures with `AttributeError: ... 'is_drill'` or `TypeError: trigger() got an unexpected keyword argument 'drill'`.

- [ ] **Step 3: Implement the drill flag on AlertCoordinator**

Edit `custom_components/shelter_finder/alert_coordinator.py`:

In `__init__`, after `self._notification_counts: dict[str, int] = {}` add:

```python
        self._is_drill: bool = False
```

After the `triggered_at` property add:

```python
    @property
    def is_drill(self) -> bool:
        return self._is_drill
```

Replace the `trigger` method with:

```python
    def trigger(self, threat_type: str, triggered_by: str = "manual", drill: bool = False) -> None:
        if threat_type not in THREAT_TYPES:
            raise ValueError(f"Unknown threat type: {threat_type}")
        self._is_active = True
        self._threat_type = threat_type
        self._triggered_by = triggered_by
        self._triggered_at = datetime.now(timezone.utc)
        self._persons_safe = []
        self._notification_counts = {p: 0 for p in self.persons}
        self._is_drill = drill
```

Replace the `cancel` method with:

```python
    def cancel(self) -> None:
        self._is_active = False
        self._threat_type = None
        self._triggered_by = None
        self._triggered_at = None
        self._persons_safe = []
        self._notification_counts = {}
        self._is_drill = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_alert_coordinator.py -v`
Expected: All tests pass (previous tests still green, 4 new drill tests pass).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/alert_coordinator.py tests/test_alert_coordinator.py
git commit -m "feat(shelter_finder): add drill flag to AlertCoordinator"
```

---

## Task 2: binary_sensor exposes drill attribute

**Files:**
- Modify: `custom_components/shelter_finder/binary_sensor.py`
- Test: `tests/test_binary_sensor.py` (create if it does not exist, otherwise append)

- [ ] **Step 1: Write the failing test**

If `tests/test_binary_sensor.py` does not exist, create it with:

```python
"""Tests for Shelter Finder binary sensor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.shelter_finder.binary_sensor import ShelterAlertBinarySensor


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = []
    return coord


@pytest.fixture
def mock_alert_coordinator():
    ac = MagicMock()
    ac.is_active = True
    ac.threat_type = "storm"
    ac.triggered_at = None
    ac.triggered_by = "service"
    ac.persons_safe = []
    ac.is_drill = False
    return ac


def test_binary_sensor_drill_attribute_false(mock_coordinator, mock_alert_coordinator):
    sensor = ShelterAlertBinarySensor(mock_coordinator, mock_alert_coordinator)
    attrs = sensor.extra_state_attributes
    assert attrs["drill"] is False


def test_binary_sensor_drill_attribute_true(mock_coordinator, mock_alert_coordinator):
    mock_alert_coordinator.is_drill = True
    sensor = ShelterAlertBinarySensor(mock_coordinator, mock_alert_coordinator)
    attrs = sensor.extra_state_attributes
    assert attrs["drill"] is True
```

If the file already exists, append only the two `test_binary_sensor_drill_attribute_*` tests (and the two fixtures if absent).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_binary_sensor.py -v -k "drill"`
Expected: 2 failures with `KeyError: 'drill'`.

- [ ] **Step 3: Add drill to extra_state_attributes**

Edit `custom_components/shelter_finder/binary_sensor.py`, replace the `extra_state_attributes` property body:

```python
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ac = self._alert_coordinator
        shelters = self.coordinator.data or []
        shelter_list = [
            {"name": s.get("name", ""), "lat": s.get("latitude"), "lon": s.get("longitude"),
             "type": s.get("shelter_type", ""), "source": s.get("source", "osm")}
            for s in shelters if s.get("latitude") and s.get("longitude")
        ]
        return {
            "threat_type": ac.threat_type,
            "triggered_at": str(ac.triggered_at) if ac.triggered_at else None,
            "triggered_by": ac.triggered_by,
            "persons_safe": ac.persons_safe,
            "drill": bool(ac.is_drill),
            "shelters": shelter_list,
            "shelter_count": len(shelter_list),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_binary_sensor.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/binary_sensor.py tests/test_binary_sensor.py
git commit -m "feat(shelter_finder): expose drill on binary_sensor.alert attributes"
```

---

## Task 3: trigger_alert service schema accepts drill

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`
- Test: `tests/test_drill_notifications.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_drill_notifications.py` with:

```python
"""Tests for drill-mode service routing and notifications."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.shelter_finder import _register_services, _send_alert_notifications
from custom_components.shelter_finder.const import DOMAIN


@pytest.fixture
def mock_hass_with_ac():
    hass = MagicMock()
    hass.services = MagicMock()
    registered: dict[str, tuple] = {}

    def register(domain, name, handler, schema=None):
        registered[name] = (handler, schema)

    hass.services.async_register.side_effect = register
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_call = AsyncMock()
    hass.services.async_services = MagicMock(return_value={"notify": {"mobile_app_alice": None}})

    ac = MagicMock()
    ac.trigger = MagicMock()
    ac.cancel = MagicMock()
    ac.is_drill = False
    ac.threat_type = "storm"
    ac.persons = ["person.alice"]

    hass.data = {DOMAIN: {"alert_coordinator": ac}}
    hass._registered = registered
    hass._ac = ac
    return hass


@pytest.mark.asyncio
async def test_trigger_alert_service_passes_drill_true(mock_hass_with_ac):
    _register_services(mock_hass_with_ac)
    handler, schema = mock_hass_with_ac._registered["trigger_alert"]

    data = schema({"threat_type": "storm", "drill": True})
    call = MagicMock()
    call.data = data

    with patch("custom_components.shelter_finder._notify_coordinators"), \
         patch("custom_components.shelter_finder._send_alert_notifications", new=AsyncMock()):
        await handler(call)

    mock_hass_with_ac._ac.trigger.assert_called_once_with(
        "storm", triggered_by="service", drill=True
    )


@pytest.mark.asyncio
async def test_trigger_alert_service_defaults_drill_false(mock_hass_with_ac):
    _register_services(mock_hass_with_ac)
    handler, schema = mock_hass_with_ac._registered["trigger_alert"]

    data = schema({"threat_type": "storm"})
    call = MagicMock()
    call.data = data

    with patch("custom_components.shelter_finder._notify_coordinators"), \
         patch("custom_components.shelter_finder._send_alert_notifications", new=AsyncMock()):
        await handler(call)

    mock_hass_with_ac._ac.trigger.assert_called_once_with(
        "storm", triggered_by="service", drill=False
    )


def test_trigger_alert_schema_rejects_non_boolean_drill(mock_hass_with_ac):
    _register_services(mock_hass_with_ac)
    _, schema = mock_hass_with_ac._registered["trigger_alert"]
    with pytest.raises(vol.Invalid):
        schema({"threat_type": "storm", "drill": "maybe"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_drill_notifications.py -v`
Expected: failures — schema does not yet accept `drill`, and handler does not forward `drill`.

- [ ] **Step 3: Update service schema and handler**

Edit `custom_components/shelter_finder/__init__.py`, replace `handle_trigger_alert` and its registration:

```python
    async def handle_trigger_alert(call: ServiceCall) -> None:
        threat_type = call.data["threat_type"]
        message = call.data.get("message", "")
        drill = call.data.get("drill", False)
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.trigger(threat_type, triggered_by="service", drill=drill)
            _notify_coordinators(hass)
            await _send_alert_notifications(hass, ac, message)
```

And in the `hass.services.async_register(DOMAIN, "trigger_alert", ...)` block, replace the schema with:

```python
    hass.services.async_register(
        DOMAIN, "trigger_alert", handle_trigger_alert,
        schema=vol.Schema({
            vol.Required("threat_type"): vol.In(THREAT_TYPES),
            vol.Optional("message", default=""): cv.string,
            vol.Optional("drill", default=False): cv.boolean,
        }),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_drill_notifications.py -v -k "service or schema"`
Expected: three tests pass.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/__init__.py tests/test_drill_notifications.py
git commit -m "feat(shelter_finder): accept drill flag on trigger_alert service"
```

---

## Task 4: Notification title and priority branch on drill

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`
- Test: `tests/test_drill_notifications.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_drill_notifications.py`:

```python
@pytest.mark.asyncio
async def test_real_alert_notification_title_and_priority():
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_call = AsyncMock()
    hass.services.async_services = MagicMock(
        return_value={"notify": {"mobile_app_alice": None}}
    )

    ac = MagicMock()
    ac.persons = ["person.alice"]
    ac.threat_type = "storm"
    ac.is_drill = False
    ac.get_best_shelter.return_value = {
        "name": "Abri A", "shelter_type": "bunker",
        "latitude": 48.85, "longitude": 2.35,
        "distance_m": 120, "eta_minutes": 2,
    }
    ac.record_notification = MagicMock()

    await _send_alert_notifications(hass, ac, "")

    args, kwargs = hass.services.async_call.call_args
    assert args[0] == "notify"
    payload = args[2]
    assert payload["title"] == "Shelter Finder - storm"
    assert payload["data"]["priority"] == "high"


@pytest.mark.asyncio
async def test_drill_alert_notification_title_and_priority():
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_call = AsyncMock()
    hass.services.async_services = MagicMock(
        return_value={"notify": {"mobile_app_alice": None}}
    )

    ac = MagicMock()
    ac.persons = ["person.alice"]
    ac.threat_type = "storm"
    ac.is_drill = True
    ac.get_best_shelter.return_value = {
        "name": "Abri A", "shelter_type": "bunker",
        "latitude": 48.85, "longitude": 2.35,
        "distance_m": 120, "eta_minutes": 2,
    }
    ac.record_notification = MagicMock()

    await _send_alert_notifications(hass, ac, "")

    args, kwargs = hass.services.async_call.call_args
    payload = args[2]
    assert payload["title"] == "[EXERCICE] Shelter Finder - storm"
    assert payload["data"]["priority"] == "normal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_drill_notifications.py -v -k "notification"`
Expected: `test_drill_alert_notification_title_and_priority` fails — current code always emits the real title and `priority: "high"`.

- [ ] **Step 3: Branch title and priority in _send_alert_notifications**

Edit `custom_components/shelter_finder/__init__.py`, replace the body of `_send_alert_notifications` from the `notif_message = ...` block through the `await hass.services.async_call(...)` call with:

```python
        notif_message = (
            f"ALERTE {alert_coordinator.threat_type.upper()}\n"
            f"Abri: {best['name']} ({best['shelter_type']})\n"
            f"Distance: {best['distance_m']}m - ETA: {best.get('eta_minutes', '?')} min\n"
        )
        if message:
            notif_message = f"{message}\n\n{notif_message}"

        if device_service is None:
            _LOGGER.warning(
                "No mobile_app notify service found for %s — "
                "check that the companion app is installed and the device name matches",
                person_id,
            )
            continue

        is_drill = bool(getattr(alert_coordinator, "is_drill", False))
        title_prefix = "[EXERCICE] " if is_drill else ""
        push_priority = "normal" if is_drill else "high"
        title = f"{title_prefix}Shelter Finder - {alert_coordinator.threat_type}"

        try:
            await hass.services.async_call(
                "notify", device_service,
                {
                    "message": notif_message,
                    "title": title,
                    "data": {
                        "actions": [{"action": "CONFIRM_SAFE", "title": "Je suis à l'abri"}],
                        "url": nav_url,
                        "clickAction": nav_url,
                        "priority": push_priority,
                        "ttl": 0,
                    },
                },
                blocking=False,
            )
            alert_coordinator.record_notification(person_id)
        except Exception:
            _LOGGER.exception("Failed to send notification to %s", person_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_drill_notifications.py -v`
Expected: all five tests pass.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/__init__.py tests/test_drill_notifications.py
git commit -m "feat(shelter_finder): drill notifications use [EXERCICE] title and normal priority"
```

---

## Task 5: ShelterDrillButton entity

**Files:**
- Modify: `custom_components/shelter_finder/button.py`
- Test: `tests/test_button.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_button.py`:

```python
from custom_components.shelter_finder.button import ShelterDrillButton


def test_drill_button_attributes(mock_coordinator, mock_alert_coordinator):
    button = ShelterDrillButton(mock_coordinator, mock_alert_coordinator)
    assert button.unique_id == "shelter_finder_drill_alert"
    assert "alert" in button.icon or "practice" in button.icon or "school" in button.icon


@pytest.mark.asyncio
async def test_drill_button_press(mock_coordinator, mock_alert_coordinator):
    button = ShelterDrillButton(mock_coordinator, mock_alert_coordinator)
    await button.async_press()
    mock_alert_coordinator.trigger.assert_called_once_with(
        "storm", triggered_by="button", drill=True
    )
    mock_coordinator.async_set_updated_data.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_button.py -v -k "drill"`
Expected: `ImportError: cannot import name 'ShelterDrillButton'`.

- [ ] **Step 3: Implement ShelterDrillButton**

Edit `custom_components/shelter_finder/button.py`. Update the imports and `async_setup_entry`, then append the new class. Replace the full file with:

```python
"""Button platform for Shelter Finder."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .alert_coordinator import AlertCoordinator
from .const import DOMAIN
from .coordinator import ShelterUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    async_add_entities([
        ShelterTriggerAlertButton(coordinator, alert_coordinator),
        ShelterCancelAlertButton(coordinator, alert_coordinator),
        ShelterDrillButton(coordinator, alert_coordinator),
    ])


class ShelterTriggerAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_trigger_alert"
    _attr_name = "Trigger alert"
    _attr_icon = "mdi:alert-plus"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        self._alert_coordinator.trigger("storm", triggered_by="button")
        self._coordinator.async_set_updated_data(self._coordinator.data or [])


class ShelterCancelAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_cancel_alert"
    _attr_name = "Cancel alert"
    _attr_icon = "mdi:alert-remove"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        self._alert_coordinator.cancel()
        self._coordinator.async_set_updated_data(self._coordinator.data or [])


class ShelterDrillButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_drill_alert"
    _attr_name = "Drill alert (exercice)"
    _attr_icon = "mdi:school-outline"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        self._alert_coordinator.trigger("storm", triggered_by="button", drill=True)
        self._coordinator.async_set_updated_data(self._coordinator.data or [])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_button.py -v`
Expected: all tests pass (existing trigger/cancel still pass, two new drill tests pass).

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/button.py tests/test_button.py
git commit -m "feat(shelter_finder): add drill button entity"
```

---

## Task 6: Lovelace map card drill banner

**Files:**
- Modify: `custom_components/shelter_finder/www/shelter-map-card.js`

The JS card has no unit test harness in this repo; verification is manual (see Step 4).

- [ ] **Step 1: Add drill styling to the stylesheet**

Edit `custom_components/shelter_finder/www/shelter-map-card.js`, in `_buildDOM`, replace the `style.textContent = ...` assignment with:

```javascript
    style.textContent =
      ":host { display: block; }" +
      "#map { width: 100%; border-radius: 0 0 12px 12px; }" +
      ".alert-banner { background: #e53e3e; color: white; text-align: center; padding: 8px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 12px 12px 0 0; display: none; }" +
      ".alert-banner.active { display: block; }" +
      ".alert-banner.drill { background: #d69e2e; }" +
      ".shelter-person-marker, .shelter-poi-marker { background: transparent !important; border: none !important; }" +
      "ha-card { overflow: hidden; }" +
      "@keyframes shelter-pulse { 0%,100% { transform:scale(1); opacity:0.25; } 50% { transform:scale(1.4); opacity:0.08; } }";
```

- [ ] **Step 2: Branch banner text and drill class in `_updateAlertBanner`**

Replace the entire `_updateAlertBanner` method with:

```javascript
  _updateAlertBanner(hass) {
    var banner = this.shadowRoot ? this.shadowRoot.querySelector("#alert-banner") : null;
    if (!banner) return;
    var alertSensor = hass.states["binary_sensor.alert"];
    var isAlert = alertSensor && alertSensor.state === "on";
    if (isAlert) {
      var attrs = alertSensor.attributes || {};
      var threatType = (attrs.threat_type || "UNKNOWN").toString().toUpperCase();
      var isDrill = attrs.drill === true;
      if (isDrill) {
        banner.textContent = "EXERCICE: " + threatType;
        banner.classList.add("drill");
      } else {
        banner.textContent = "ALERTE: " + threatType;
        banner.classList.remove("drill");
      }
      banner.classList.add("active");
    } else {
      banner.classList.remove("active");
      banner.classList.remove("drill");
    }
  }
```

- [ ] **Step 3: Bump the card version log**

Near the bottom of the file, replace:

```javascript
console.info(
  "%c SHELTER-MAP-CARD %c v0.5.0 ",
  "background:#3182ce;color:white;font-weight:bold;padding:2px 6px;border-radius:3px 0 0 3px",
  "background:#e2e8f0;padding:2px 6px;border-radius:0 3px 3px 0"
);
```

With:

```javascript
console.info(
  "%c SHELTER-MAP-CARD %c v0.6.0-drill ",
  "background:#3182ce;color:white;font-weight:bold;padding:2px 6px;border-radius:3px 0 0 3px",
  "background:#e2e8f0;padding:2px 6px;border-radius:0 3px 3px 0"
);
```

- [ ] **Step 4: Manual verification**

In a running HA dev instance with the component installed:

1. Hard-refresh the dashboard (Ctrl+Shift+R) so the new JS loads (check the console banner shows `v0.6.0-drill`).
2. Developer Tools > Services > `shelter_finder.trigger_alert` with `threat_type: storm`, `drill: true`. Expected: yellow (#d69e2e) banner reading `EXERCICE: STORM`.
3. `shelter_finder.cancel_alert`. Expected: banner hidden.
4. `shelter_finder.trigger_alert` with `threat_type: storm` (no drill). Expected: red (#e53e3e) banner reading `ALERTE: STORM`.

- [ ] **Step 5: Commit**

```bash
git add custom_components/shelter_finder/www/shelter-map-card.js
git commit -m "feat(shelter-map-card): yellow EXERCICE banner when drill attribute is true"
```

---

## Task 7: Full suite green + behavior-table sanity check

**Files:** (none modified)

- [ ] **Step 1: Run the entire Python test suite**

Run: `pytest -v`
Expected: every test passes. No warnings about unknown kwargs or schema violations.

- [ ] **Step 2: Cross-check the spec's behavior table**

Open `docs/superpowers/specs/2026-04-13-v0.6-features-design.md` lines 194-205 and tick each row against the implementation:

- Shelter scoring: `AlertCoordinator.get_best_shelter` unchanged — same scoring in drill. PASS.
- Map banner: yellow + "EXERCICE: {TYPE}" when `drill === true`, red + "ALERTE: {TYPE}" otherwise — Task 6. PASS.
- Push notification title: `[EXERCICE] Shelter Finder - {type}` vs `Shelter Finder - {type}` — Task 4. PASS.
- Push priority: `normal` vs `high` — Task 4. PASS.
- TTS prefix: TTS service not yet implemented in this plan (Feature 4, separate plan). Drill propagation is ready via `ac.is_drill` for the TTS plan to consume. PASS.
- Sensors update normally: no sensor files touched. PASS.
- `binary_sensor.alert` state `on`: `is_on` unchanged. PASS.
- `binary_sensor.alert` attribute `drill`: Task 2. PASS.

- [ ] **Step 3: Commit (if the sanity check revealed a gap, fix and commit; else skip)**

If all rows pass, no commit needed. Otherwise:

```bash
git add -A
git commit -m "fix(shelter_finder): address drill behavior-table gap"
```

---

## Self-Review Notes

- **Spec coverage:** every bullet of spec lines 176-225 is mapped to a task except the TTS-prefix row, which is explicitly out of scope per the spec (Feature 4 lives in its own plan) — the hook (`ac.is_drill`) is in place for that plan.
- **Type consistency:** `drill: bool` keyword argument used consistently across `AlertCoordinator.trigger`, service schema (`cv.boolean`), `ShelterDrillButton.async_press`, and `ac.is_drill` property. Button unique_id `shelter_finder_drill_alert` is a new namespaced value (no collision with `trigger_alert` / `cancel_alert`).
- **No placeholders:** every step contains runnable code or a concrete command.
- **File touches only what the spec lists:** alert_coordinator, binary_sensor, __init__, button, shelter-map-card.js, two test files, plus the new `test_drill_notifications.py` and (if missing) `test_binary_sensor.py`. No OptionsFlow, no const.py (drill is not config).
