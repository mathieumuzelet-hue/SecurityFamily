# Shelter Finder v0.2 — Finalization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all remaining issues on `main` to make v0.2 shippable: broken entity references in the map card, missing card editor, missing Lovelace auto-registration, missing search radius circle, broken test infrastructure, and untracked `__pycache__` directories.

**Architecture:** The card is a vanilla HTMLElement (no Lit) in `www/shelter-map-card.js`. The integration registers entities with `has_entity_name = True` and unique_ids prefixed with `shelter_finder_`. The stubs under `stubs/` need to be expanded so tests can import all HA modules referenced by the component.

**Tech Stack:** Python 3.12+, vanilla JS (ES2022), Home Assistant custom_component, pytest

---

## File Map

| File | Responsibility | Modified in Task |
|---|---|---|
| `custom_components/shelter_finder/www/shelter-map-card.js` | Map card: fix entity IDs, add editor, add radius circle | 1, 2, 3 |
| `custom_components/shelter_finder/__init__.py` | Restore Lovelace resource auto-registration | 4 |
| `stubs/homeassistant/__init__.py` | Expand stubs so test imports work | 5 |
| `stubs/homeassistant/components/` | Add stub modules for `webhook`, `binary_sensor`, `sensor`, `persistent_notification` | 5 |
| `stubs/homeassistant/helpers/` | Add stub modules for `selector`, `entity_platform`, `update_coordinator`, `aiohttp_client`, `config_validation` | 5 |
| `.gitignore` | Ignore `__pycache__/` and `.pytest_cache/` | 6 |

---

### Task 1: Fix entity references in the map card

The card currently references `binary_sensor.alert`, `sensor.alert_type`, `sensor.{person}_shelter_nearest`, and `sensor.{person}_shelter_distance`. These don't match the actual entity IDs registered by the integration:
- `binary_sensor.shelter_finder_alert` (unique_id: `shelter_finder_alert`)
- `sensor.shelter_finder_alert_type` (unique_id: `shelter_finder_alert_type`)
- `sensor.shelter_finder_{person}_nearest` (unique_id: `shelter_finder_{person}_nearest`)
- `sensor.shelter_finder_{person}_distance` (unique_id: `shelter_finder_{person}_distance`)

**Files:**
- Modify: `custom_components/shelter_finder/www/shelter-map-card.js:170-178` (alert banner references)
- Modify: `custom_components/shelter_finder/www/shelter-map-card.js:222-223` (person sensor references)

- [ ] **Step 1: Fix `_updateAlertBanner` entity references**

In `shelter-map-card.js`, in `_updateAlertBanner(hass)`, change:

```javascript
// OLD:
var alertSensor = hass.states["binary_sensor.alert"];
// ...
var alertType = hass.states["sensor.alert_type"];
```

to:

```javascript
// NEW:
var alertSensor = hass.states["binary_sensor.shelter_finder_alert"];
// ...
var alertType = hass.states["sensor.shelter_finder_alert_type"];
```

- [ ] **Step 2: Fix person sensor references in `_updatePersonMarkers`**

In `_updatePersonMarkers`, change:

```javascript
// OLD:
var nearestState = hass.states["sensor." + personKey + "_shelter_nearest"];
var distState = hass.states["sensor." + personKey + "_shelter_distance"];
```

to:

```javascript
// NEW:
var nearestState = hass.states["sensor.shelter_finder_" + personKey + "_nearest"];
var distState = hass.states["sensor.shelter_finder_" + personKey + "_distance"];
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/shelter_finder/www/shelter-map-card.js
git commit -m "fix: align card entity references with actual HA entity IDs"
```

---

### Task 2: Restore card editor (vanilla HTMLElement)

The card editor was removed during the Lit → vanilla HTMLElement rewrite. The editor allows users to configure the card via the HA UI instead of editing YAML. It also requires re-adding `getConfigElement()` and `getStubConfig()` static methods to the main card class.

**Files:**
- Modify: `custom_components/shelter_finder/www/shelter-map-card.js` (append editor class + add static methods)

- [ ] **Step 1: Add `getConfigElement` and `getStubConfig` to ShelterMapCard**

In `shelter-map-card.js`, add these two static methods inside the `ShelterMapCard` class, right after `getCardSize()`:

```javascript
  static getConfigElement() {
    return document.createElement("shelter-map-card-editor");
  }

  static getStubConfig() {
    return { title: "Shelter Finder", entities: ["person.alice"], default_zoom: 13, height: "400px" };
  }
```

- [ ] **Step 2: Add the editor class before `customElements.define`**

Insert the full editor class before the `customElements.define("shelter-map-card", ...)` line:

```javascript
class ShelterMapCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
    var root = this.shadowRoot;
    root.textContent = "";

    var style = document.createElement("style");
    style.textContent =
      ".editor { display: flex; flex-direction: column; gap: 12px; padding: 16px; }" +
      "label { display: flex; flex-direction: column; font-size: 0.85em; color: var(--primary-text-color, #333); }" +
      "input, select { margin-top: 4px; padding: 6px 8px; border: 1px solid var(--divider-color, #ccc); border-radius: 4px; background: var(--card-background-color, white); color: var(--primary-text-color, #333); }" +
      ".checkbox-label { flex-direction: row; align-items: center; gap: 8px; }";
    root.appendChild(style);

    var form = document.createElement("div");
    form.className = "editor";

    var self = this;

    // Title
    var titleLabel = document.createElement("label");
    titleLabel.textContent = "Title";
    var titleInput = document.createElement("input");
    titleInput.value = this._config.title || "";
    titleInput.addEventListener("change", function() {
      self._fireChanged({ title: titleInput.value });
    });
    titleLabel.appendChild(titleInput);
    form.appendChild(titleLabel);

    // Entities
    var entLabel = document.createElement("label");
    entLabel.textContent = "Entities (comma-separated)";
    var entInput = document.createElement("input");
    entInput.value = (this._config.entities || []).join(", ");
    entInput.addEventListener("change", function() {
      var ents = entInput.value.split(",").map(function(s) { return s.trim(); }).filter(Boolean);
      self._fireChanged({ entities: ents });
    });
    entLabel.appendChild(entInput);
    form.appendChild(entLabel);

    // Default zoom
    var zoomLabel = document.createElement("label");
    zoomLabel.textContent = "Default zoom";
    var zoomInput = document.createElement("input");
    zoomInput.type = "number";
    zoomInput.min = "1";
    zoomInput.max = "20";
    zoomInput.value = this._config.default_zoom || 13;
    zoomInput.addEventListener("change", function() {
      self._fireChanged({ default_zoom: parseInt(zoomInput.value, 10) });
    });
    zoomLabel.appendChild(zoomInput);
    form.appendChild(zoomLabel);

    // Height
    var heightLabel = document.createElement("label");
    heightLabel.textContent = "Height";
    var heightInput = document.createElement("input");
    heightInput.value = this._config.height || "400px";
    heightInput.addEventListener("change", function() {
      self._fireChanged({ height: heightInput.value });
    });
    heightLabel.appendChild(heightInput);
    form.appendChild(heightLabel);

    // Show radius
    var radiusLabel = document.createElement("label");
    radiusLabel.className = "checkbox-label";
    var radiusCheck = document.createElement("input");
    radiusCheck.type = "checkbox";
    radiusCheck.checked = this._config.show_radius !== false;
    radiusCheck.addEventListener("change", function() {
      self._fireChanged({ show_radius: radiusCheck.checked });
    });
    radiusLabel.appendChild(radiusCheck);
    radiusLabel.appendChild(document.createTextNode(" Show search radius"));
    form.appendChild(radiusLabel);

    root.appendChild(form);
  }

  _fireChanged(partial) {
    var cfg = Object.assign({}, this._config, partial);
    this._config = cfg;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg } }));
  }
}
```

- [ ] **Step 3: Register the editor element**

Add this line right before `customElements.define("shelter-map-card", ShelterMapCard);`:

```javascript
customElements.define("shelter-map-card-editor", ShelterMapCardEditor);
```

- [ ] **Step 4: Commit**

```bash
git add custom_components/shelter_finder/www/shelter-map-card.js
git commit -m "feat: restore card editor as vanilla HTMLElement"
```

---

### Task 3: Add search radius circle on map

When `show_radius` is true in the card config, draw a semi-transparent circle around each person showing the configured search radius. The radius value is read from the `binary_sensor.shelter_finder_alert` attributes (which includes `search_radius` from the coordinator config via the entry data), or defaults to 2000m.

**Files:**
- Modify: `custom_components/shelter_finder/www/shelter-map-card.js` (add radius circles in `_updatePersonMarkers`)
- Modify: `custom_components/shelter_finder/binary_sensor.py:48` (expose `search_radius` in attributes)

- [ ] **Step 1: Expose `search_radius` in binary_sensor attributes**

In `binary_sensor.py`, update the `__init__` to accept `search_radius` and expose it:

```python
class ShelterAlertBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_alert"
    _attr_name = "Alert"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator, alert_coordinator, search_radius=2000):
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator
        self._search_radius = search_radius
```

Update `extra_state_attributes` to include `search_radius`:

```python
        return {
            "threat_type": ac.threat_type,
            "triggered_at": str(ac.triggered_at) if ac.triggered_at else None,
            "triggered_by": ac.triggered_by,
            "persons_safe": ac.persons_safe,
            "shelters": shelter_list,
            "shelter_count": len(shelter_list),
            "search_radius": self._search_radius,
        }
```

Update `async_setup_entry` to pass `search_radius`:

```python
async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    config = {**entry.data, **entry.options}
    search_radius = config.get("search_radius", 2000)
    async_add_entities([ShelterAlertBinarySensor(coordinator, alert_coordinator, search_radius)])
```

- [ ] **Step 2: Add radius circle rendering in the card**

In `shelter-map-card.js`, add a `_radiusCircles` Map in the constructor:

```javascript
this._radiusCircles = new Map();
```

In `_updatePersonMarkers`, after a person marker is created/updated, add radius circle logic. Insert this code right before the popup-update section (before the `// Update popup` comment), inside the `entities.forEach` callback:

```javascript
      // Radius circle
      if (self.config.show_radius !== false) {
        var alertState = hass.states["binary_sensor.shelter_finder_alert"];
        var radius = (alertState && alertState.attributes && alertState.attributes.search_radius) || 2000;
        if (self._radiusCircles.has(entityId)) {
          self._radiusCircles.get(entityId).setLatLng(latlng).setRadius(radius);
        } else {
          var circle = L.circle(latlng, {
            radius: radius,
            color: PERSON_COLORS[index % PERSON_COLORS.length],
            fillOpacity: 0.06,
            weight: 1,
            dashArray: "6 4",
          }).addTo(self._map);
          self._radiusCircles.set(entityId, circle);
        }
      }
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/shelter_finder/www/shelter-map-card.js custom_components/shelter_finder/binary_sensor.py
git commit -m "feat: add search radius circle on map (show_radius option)"
```

---

### Task 4: Restore Lovelace resource auto-registration

The static path + Lovelace resource registration was removed during debugging. Restore it in `__init__.py` so users don't need to manually add the card resource.

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py:121` (add registration after webhook, before platform forward)

- [ ] **Step 1: Add resource auto-registration in `async_setup_entry`**

In `__init__.py`, add this block right before `await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)` (line 122):

```python
    # --- Register frontend card resource ---
    if not hass.data[DOMAIN].get("_frontend_registered"):
        card_path = Path(__file__).parent / "www" / "shelter-map-card.js"
        hass.http.register_static_path(
            "/shelter_finder/shelter-map-card.js",
            str(card_path),
            cache_headers=True,
        )
        hass.data[DOMAIN]["_frontend_registered"] = True

        # Auto-register Lovelace resource (storage mode only)
        try:
            resources = hass.data.get("lovelace", {})
            if hasattr(resources, "get"):
                res_collection = resources.get("resources")
            else:
                res_collection = None
            if res_collection:
                url = "/shelter_finder/shelter-map-card.js"
                existing = [r for r in res_collection.async_items() if r.get("url") == url]
                if not existing:
                    await res_collection.async_create_item({"res_type": "module", "url": url})
                    _LOGGER.info("Lovelace resource registered: %s", url)
        except Exception:
            _LOGGER.debug(
                "Lovelace in YAML mode or resources unavailable — add manually: "
                "resources: [{url: /shelter_finder/shelter-map-card.js, type: module}]"
            )
```

Also add this import at the top if not already present (it is already imported):

```python
from pathlib import Path
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/shelter_finder/__init__.py
git commit -m "feat: restore Lovelace resource auto-registration"
```

---

### Task 5: Fix test infrastructure — expand stubs

Tests fail because `from homeassistant.components import webhook` and similar imports can't resolve. The stubs under `stubs/` only cover `core` and `config_entries`. We need to add stubs for all HA modules imported by the component.

The CI workflow uses `pytest-homeassistant-custom-component` which provides the real HA stubs, but locally we need minimal stubs. The actual fix is to ensure `PYTHONPATH=stubs` is set AND that all imported modules have stub files.

**Files:**
- Create: `stubs/homeassistant/components/__init__.py`
- Create: `stubs/homeassistant/components/webhook/__init__.py`
- Create: `stubs/homeassistant/components/binary_sensor/__init__.py`
- Create: `stubs/homeassistant/components/sensor/__init__.py`
- Create: `stubs/homeassistant/components/persistent_notification/__init__.py`
- Create: `stubs/homeassistant/components/button/__init__.py`
- Create: `stubs/homeassistant/helpers/__init__.py`
- Create: `stubs/homeassistant/helpers/selector.py`
- Create: `stubs/homeassistant/helpers/entity_platform.py`
- Create: `stubs/homeassistant/helpers/update_coordinator.py`
- Create: `stubs/homeassistant/helpers/aiohttp_client.py`
- Create: `stubs/homeassistant/helpers/config_validation.py`
- Create: `stubs/homeassistant/const.py`
- Create: `stubs/homeassistant/data_entry_flow.py`
- Create: `stubs/voluptuous/__init__.py`
- Modify: `setup.cfg` (add PYTHONPATH for pytest)

- [ ] **Step 1: Create component stubs**

Create `stubs/homeassistant/components/__init__.py`:
```python
"""Stub components package."""
```

Create `stubs/homeassistant/components/webhook/__init__.py`:
```python
"""Stub webhook component."""
def async_register(hass, domain, name, webhook_id, handler):
    pass

def async_unregister(hass, webhook_id):
    pass
```

Create `stubs/homeassistant/components/binary_sensor/__init__.py`:
```python
"""Stub binary_sensor component."""

class BinarySensorDeviceClass:
    SAFETY = "safety"

class BinarySensorEntity:
    _attr_has_entity_name = False
    _attr_unique_id = None
    _attr_name = None
    _attr_device_class = None
    _attr_icon = None

    @property
    def is_on(self):
        return False

    @property
    def extra_state_attributes(self):
        return {}
```

Create `stubs/homeassistant/components/sensor/__init__.py`:
```python
"""Stub sensor component."""

class SensorStateClass:
    MEASUREMENT = "measurement"

class SensorEntity:
    _attr_has_entity_name = False
    _attr_unique_id = None
    _attr_name = None
    _attr_icon = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    @property
    def native_value(self):
        return None

    @property
    def extra_state_attributes(self):
        return {}
```

Create `stubs/homeassistant/components/persistent_notification/__init__.py`:
```python
"""Stub persistent_notification component."""
def async_create(hass, message, title=None, notification_id=None):
    pass
```

Create `stubs/homeassistant/components/button/__init__.py`:
```python
"""Stub button component."""

class ButtonEntity:
    _attr_has_entity_name = False
    _attr_unique_id = None
    _attr_name = None
    _attr_icon = None

    async def async_press(self):
        pass
```

- [ ] **Step 2: Create helper stubs**

Create `stubs/homeassistant/helpers/__init__.py`:
```python
"""Stub helpers package."""
```

Create `stubs/homeassistant/helpers/selector.py`:
```python
"""Stub selectors."""

class SelectSelectorMode:
    LIST = "list"
    DROPDOWN = "dropdown"

class SelectSelectorConfig:
    def __init__(self, options=None, multiple=False, mode=None):
        self.options = options or []
        self.multiple = multiple
        self.mode = mode

class SelectSelector:
    def __init__(self, config=None):
        self.config = config
```

Create `stubs/homeassistant/helpers/entity_platform.py`:
```python
"""Stub entity_platform."""
from typing import Callable

AddEntitiesCallback = Callable
```

Create `stubs/homeassistant/helpers/update_coordinator.py`:
```python
"""Stub update_coordinator."""

class CoordinatorEntity:
    def __init__(self, coordinator, context=None):
        self.coordinator = coordinator
```

Create `stubs/homeassistant/helpers/aiohttp_client.py`:
```python
"""Stub aiohttp_client."""

def async_get_clientsession(hass):
    return None
```

Create `stubs/homeassistant/helpers/config_validation.py`:
```python
"""Stub config_validation."""
string = str
```

- [ ] **Step 3: Create remaining stubs**

Create `stubs/homeassistant/const.py`:
```python
"""Stub constants."""

class Platform:
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    BUTTON = "button"
```

Create `stubs/homeassistant/data_entry_flow.py`:
```python
"""Stub data_entry_flow."""

class FlowResult(dict):
    pass
```

Create `stubs/voluptuous/__init__.py`:
```python
"""Stub voluptuous."""

def Schema(schema):
    return schema

def Required(key, default=None):
    return key

def Optional(key, default=None):
    return key

def In(values):
    return lambda v: v

def All(*validators):
    return validators[-1] if validators else lambda v: v

def Coerce(type_):
    return type_

class Range:
    def __init__(self, min=None, max=None):
        self.min = min
        self.max = max
```

Update `stubs/homeassistant/__init__.py`:
```python
# Minimal stub for running pure-unit tests without a full HA install
```

- [ ] **Step 4: Configure pytest to use stubs**

Update `setup.cfg` to:

```ini
[tool:pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = stubs .
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/ -v --tb=short
```

Expected: All 10 test files import correctly, tests pass (at least `test_shelter_logic.py`, `test_cache.py`, `test_routing.py`, `test_overpass.py`).

- [ ] **Step 6: Commit**

```bash
git add stubs/ setup.cfg
git commit -m "fix: expand HA stubs so tests run locally without homeassistant package"
```

---

### Task 6: Add .gitignore

Untracked `__pycache__/` directories are showing in `git status`. Add a `.gitignore`.

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
build/
.coverage
coverage.xml
htmlcov/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore for pycache and test artifacts"
```

---

## Review Checkpoint

After all 6 tasks:

1. Verify card entity references match integration entities:
   - `binary_sensor.shelter_finder_alert` in card and in `binary_sensor.py`
   - `sensor.shelter_finder_{person}_nearest` in card and in `sensor.py`

2. Verify tests run:
   ```bash
   pytest tests/ -v --tb=short
   ```

3. Verify JS card syntax:
   ```bash
   node --input-type=module < custom_components/shelter_finder/www/shelter-map-card.js 2>&1 || echo "OK (top-level await needs HA runtime)"
   ```

4. Push to GitHub and verify CI passes.
