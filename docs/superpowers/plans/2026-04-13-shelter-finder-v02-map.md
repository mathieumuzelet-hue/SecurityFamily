# Shelter Finder v0.2 — Lovelace Map Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Lovelace custom card that displays household members and nearby shelters on an interactive Leaflet map, with auto-discovery in HA's "Add card" dialog.

**Architecture:** Single JS file (`shelter-map-card.js`) using Lit Element for the HA card lifecycle and Leaflet.js (loaded dynamically from CDN) for the map. The card reads `person.*` and `sensor.shelter_finder_*` entity states via the `hass` object. Leaflet CSS is injected into the Shadow DOM via `adoptedStyleSheets`. The integration's `__init__.py` auto-registers the JS resource so users never touch config files.

**Tech Stack:** Lit Element (from HA's bundled copy), Leaflet.js 1.9.4 (ESM CDN), vanilla JS (ES2022, no build step)

**Design doc:** `docs/superpowers/specs/2026-04-13-shelter-finder-design.md` — Section 6

---

## File Map

| File | Responsibility | Created in Task |
|---|---|---|
| `custom_components/shelter_finder/www/shelter-map-card.js` | Main card: map, markers, popups, auto-discovery | 1-4 |
| `custom_components/shelter_finder/__init__.py` | Add static path + Lovelace resource registration | 5 |
| `custom_components/shelter_finder/manifest.json` | Add `frontend` dependency | 5 |

---

### Task 1: Card Shell + Leaflet Map Init

**Files:**
- Create: `custom_components/shelter_finder/www/shelter-map-card.js`

- [ ] **Step 1: Create the www directory**

```bash
mkdir -p custom_components/shelter_finder/www
```

- [ ] **Step 2: Write the card shell with Leaflet initialization**

Create `custom_components/shelter_finder/www/shelter-map-card.js`:

```javascript
// Shelter Finder Map Card — Lovelace custom card
// Loaded as ES module from /shelter_finder/shelter-map-card.js

// ─── Lit Element import (use HA's bundled copy) ───────────────────────────────
const LitModule = await (async () => {
  try {
    return await import("/frontend_latest/lit.js");
  } catch {
    // Fallback for dev/testing
    return await import("https://cdn.jsdelivr.net/npm/lit@3/+esm");
  }
})();

const { LitElement, html, css, nothing } = LitModule;

// ─── Leaflet lazy loader ──────────────────────────────────────────────────────
const LEAFLET_CSS_URL =
  "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS_URL =
  "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet-src.esm.js";

let _leafletPromise = null;
function loadLeaflet() {
  if (!_leafletPromise) {
    _leafletPromise = import(LEAFLET_JS_URL).then((m) => m.default);
  }
  return _leafletPromise;
}

async function injectLeafletCSS(shadowRoot) {
  if ("adoptedStyleSheets" in Document.prototype) {
    const sheet = new CSSStyleSheet();
    const cssText = await fetch(LEAFLET_CSS_URL).then((r) => r.text());
    await sheet.replace(cssText);
    shadowRoot.adoptedStyleSheets = [...shadowRoot.adoptedStyleSheets, sheet];
  } else {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = LEAFLET_CSS_URL;
    shadowRoot.appendChild(link);
  }
}

// ─── Shelter icon definitions ─────────────────────────────────────────────────
const SHELTER_ICONS = {
  bunker: { icon: "mdi:shield", color: "#e53e3e" },
  subway: { icon: "mdi:train-variant", color: "#3182ce" },
  civic: { icon: "mdi:office-building", color: "#38a169" },
  school: { icon: "mdi:school", color: "#d69e2e" },
  worship: { icon: "mdi:church", color: "#805ad5" },
  shelter: { icon: "mdi:home-roof", color: "#718096" },
  sports: { icon: "mdi:dumbbell", color: "#dd6b20" },
  hospital: { icon: "mdi:hospital-box", color: "#e53e3e" },
  government: { icon: "mdi:bank", color: "#2d3748" },
  open_space: { icon: "mdi:pine-tree", color: "#48bb78" },
};

const PERSON_COLORS = [
  "#3182ce",
  "#e53e3e",
  "#38a169",
  "#d69e2e",
  "#805ad5",
  "#dd6b20",
  "#319795",
  "#b83280",
];

// ─── Helper: create colored circle marker for a person ────────────────────────
function createPersonIcon(L, name, colorIndex) {
  const color = PERSON_COLORS[colorIndex % PERSON_COLORS.length];
  const initial = (name || "?")[0].toUpperCase();
  return L.divIcon({
    className: "shelter-person-marker",
    html: `<div style="
      background:${color};
      color:white;
      width:32px;height:32px;
      border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-weight:bold;font-size:14px;
      border:2px solid white;
      box-shadow:0 2px 6px rgba(0,0,0,0.3);
    ">${initial}</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
}

// ─── Helper: create shelter marker icon ───────────────────────────────────────
function createShelterIcon(L, shelterType) {
  const cfg = SHELTER_ICONS[shelterType] || SHELTER_ICONS.shelter;
  return L.divIcon({
    className: "shelter-poi-marker",
    html: `<div style="
      background:${cfg.color};
      color:white;
      width:24px;height:24px;
      border-radius:4px;
      display:flex;align-items:center;justify-content:center;
      font-size:14px;
      border:1px solid white;
      box-shadow:0 1px 4px rgba(0,0,0,0.3);
      opacity:0.85;
    ">&#9978;</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14],
  });
}

// ─── Main Card ────────────────────────────────────────────────────────────────
class ShelterMapCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      config: { attribute: false },
    };
  }

  constructor() {
    super();
    this._hass = null;
    this._map = null;
    this._L = null;
    this._personMarkers = new Map();
    this._shelterMarkers = new Map();
    this._radiusCircle = null;
    this._fitted = false;
  }

  setConfig(config) {
    if (!config.entities || !config.entities.length) {
      throw new Error("shelter-map-card: define at least one entity in 'entities'");
    }
    this.config = {
      title: "Shelter Finder",
      default_zoom: 13,
      alert_zoom: 15,
      height: "400px",
      show_radius: true,
      ...config,
    };
  }

  set hass(hass) {
    const old = this._hass;
    this._hass = hass;
    if (this._map && this._L) {
      this._updatePersonMarkers(hass, old);
      this._updateShelterMarkers(hass);
    }
    this.requestUpdate("hass", old);
  }

  get hass() {
    return this._hass;
  }

  async firstUpdated() {
    await injectLeafletCSS(this.shadowRoot);
    this._L = await loadLeaflet();

    const container = this.shadowRoot.querySelector("#map");
    this._map = this._L.map(container, {
      zoomControl: true,
      attributionControl: true,
    });

    this._L
      .tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19,
      })
      .addTo(this._map);

    if (this._hass) {
      this._updatePersonMarkers(this._hass, null);
      this._updateShelterMarkers(this._hass);
    }
  }

  _updatePersonMarkers(hass, prevHass) {
    const L = this._L;
    const entities = this.config.entities || [];
    const bounds = [];

    entities.forEach((entityId, index) => {
      const stateObj = hass.states[entityId];
      if (!stateObj) return;

      const { latitude, longitude, friendly_name } = stateObj.attributes;
      if (latitude == null || longitude == null) return;

      const latlng = [latitude, longitude];
      bounds.push(latlng);

      // Skip update if position unchanged
      const prev = prevHass?.states[entityId];
      if (
        prev &&
        prev.attributes.latitude === latitude &&
        prev.attributes.longitude === longitude
      ) {
        return;
      }

      if (this._personMarkers.has(entityId)) {
        this._personMarkers.get(entityId).setLatLng(latlng);
      } else {
        const name = friendly_name || entityId.split(".").pop();
        const icon = createPersonIcon(L, name, index);
        const marker = L.marker(latlng, { icon, title: name, zIndexOffset: 1000 })
          .bindPopup(`<b>${name}</b>`)
          .addTo(this._map);
        this._personMarkers.set(entityId, marker);
      }

      // Update popup
      const name = friendly_name || entityId.split(".").pop();
      const nearestSensor = `sensor.shelter_finder_${entityId.split(".").pop()}_nearest`;
      const distSensor = `sensor.shelter_finder_${entityId.split(".").pop()}_distance`;
      const nearestState = hass.states[nearestSensor];
      const distState = hass.states[distSensor];

      let popupHtml = `<b>${name}</b>`;
      if (nearestState && nearestState.state !== "unknown" && nearestState.state !== "unavailable") {
        popupHtml += `<br>Nearest: ${nearestState.state}`;
        if (distState && distState.state !== "unknown") {
          popupHtml += ` (${distState.state}m)`;
        }
      }
      this._personMarkers.get(entityId)?.getPopup()?.setContent(popupHtml);
    });

    // Fit bounds on first load
    if (!this._fitted && bounds.length) {
      this._fitted = true;
      if (bounds.length === 1) {
        this._map.setView(bounds[0], Number(this.config.default_zoom));
      } else {
        this._map.fitBounds(bounds, { padding: [40, 40] });
      }
    }
  }

  _updateShelterMarkers(hass) {
    const L = this._L;

    // Find all shelter_finder nearest sensors to get shelter data from attributes
    const shelterEntities = Object.keys(hass.states).filter(
      (id) => id.startsWith("sensor.shelter_finder_") && id.endsWith("_nearest")
    );

    const seenIds = new Set();

    for (const sensorId of shelterEntities) {
      const state = hass.states[sensorId];
      if (!state || state.state === "unknown" || state.state === "unavailable") continue;

      const { latitude, longitude, shelter_type, source } = state.attributes;
      if (latitude == null || longitude == null) continue;

      const markerId = `${latitude},${longitude}`;
      if (seenIds.has(markerId)) continue;
      seenIds.add(markerId);

      if (!this._shelterMarkers.has(markerId)) {
        const icon = createShelterIcon(L, shelter_type || "shelter");
        const marker = L.marker([latitude, longitude], { icon })
          .bindPopup(
            `<b>${state.state}</b><br>Type: ${shelter_type || "unknown"}<br>Source: ${source || "osm"}`
          )
          .addTo(this._map);
        this._shelterMarkers.set(markerId, marker);
      }
    }
  }

  render() {
    const alertSensor = this._hass?.states["binary_sensor.shelter_finder_alert"];
    const isAlert = alertSensor?.state === "on";
    const alertType = this._hass?.states["sensor.shelter_finder_alert_type"]?.state;

    return html`
      ${isAlert
        ? html`<div class="alert-banner">
            ALERTE: ${alertType?.toUpperCase() || "UNKNOWN"}
          </div>`
        : nothing}
      <ha-card header=${this.config?.title ?? "Shelter Finder"}>
        <div id="map" style="height:${this.config?.height ?? "400px"}"></div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      :host {
        display: block;
      }
      #map {
        width: 100%;
        border-radius: 0 0 var(--ha-card-border-radius, 12px)
          var(--ha-card-border-radius, 12px);
      }
      .alert-banner {
        background: #e53e3e;
        color: white;
        text-align: center;
        padding: 8px;
        font-weight: bold;
        font-size: 14px;
        letter-spacing: 1px;
        border-radius: var(--ha-card-border-radius, 12px)
          var(--ha-card-border-radius, 12px) 0 0;
      }
      .shelter-person-marker,
      .shelter-poi-marker {
        background: transparent !important;
        border: none !important;
      }
    `;
  }

  getCardSize() {
    return 5;
  }

  static getConfigElement() {
    return document.createElement("shelter-map-card-editor");
  }

  static getStubConfig() {
    return {
      title: "Shelter Finder",
      entities: ["person.alice"],
      default_zoom: 13,
    };
  }
}

// ─── Card Editor ──────────────────────────────────────────────────────────────
class ShelterMapCardEditor extends LitElement {
  static get properties() {
    return { hass: {}, _config: { state: true } };
  }

  setConfig(config) {
    this._config = config;
  }

  _valueChanged(ev) {
    const cfg = { ...this._config, [ev.target.name]: ev.target.value };
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: cfg } })
    );
  }

  render() {
    if (!this._config) return nothing;
    return html`
      <div class="editor">
        <label
          >Title
          <input
            name="title"
            .value=${this._config.title ?? ""}
            @change=${this._valueChanged}
          />
        </label>
        <label
          >Entities (comma-separated)
          <input
            name="_entities_raw"
            .value=${(this._config.entities ?? []).join(", ")}
            @change=${(ev) => {
              const cfg = {
                ...this._config,
                entities: ev.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              };
              this.dispatchEvent(
                new CustomEvent("config-changed", { detail: { config: cfg } })
              );
            }}
          />
        </label>
        <label
          >Default zoom
          <input
            type="number"
            name="default_zoom"
            .value=${this._config.default_zoom ?? 13}
            @change=${this._valueChanged}
          />
        </label>
        <label
          >Height
          <input
            name="height"
            .value=${this._config.height ?? "400px"}
            @change=${this._valueChanged}
          />
        </label>
        <label>
          <input
            type="checkbox"
            name="show_radius"
            .checked=${this._config.show_radius ?? true}
            @change=${(ev) => {
              const cfg = {
                ...this._config,
                show_radius: ev.target.checked,
              };
              this.dispatchEvent(
                new CustomEvent("config-changed", { detail: { config: cfg } })
              );
            }}
          />
          Show search radius
        </label>
      </div>
    `;
  }

  static get styles() {
    return css`
      .editor {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 16px;
      }
      label {
        display: flex;
        flex-direction: column;
        font-size: 0.85em;
      }
      input[type="text"],
      input[type="number"],
      input:not([type]) {
        margin-top: 4px;
        padding: 6px 8px;
        border: 1px solid var(--divider-color, #ccc);
        border-radius: 4px;
      }
    `;
  }
}

// ─── Register elements ────────────────────────────────────────────────────────
customElements.define("shelter-map-card-editor", ShelterMapCardEditor);
customElements.define("shelter-map-card", ShelterMapCard);

// ─── Auto-discovery ───────────────────────────────────────────────────────────
window.customCards = window.customCards || [];
window.customCards.push({
  type: "shelter-map-card",
  name: "Shelter Finder Map",
  description: "Carte des abris et membres du foyer",
  preview: true,
});

console.info(
  "%c SHELTER-MAP-CARD %c loaded ",
  "background:#3182ce;color:white;font-weight:bold;padding:2px 6px;border-radius:3px 0 0 3px",
  "background:#e2e8f0;padding:2px 6px;border-radius:0 3px 3px 0"
);
```

- [ ] **Step 3: Verify the file exists and check size**

```bash
ls -la custom_components/shelter_finder/www/shelter-map-card.js
wc -c custom_components/shelter_finder/www/shelter-map-card.js
```

Expected: file exists, < 50KB

- [ ] **Step 4: Commit**

```bash
git add custom_components/shelter_finder/www/shelter-map-card.js
git commit -m "feat: add Lovelace custom card with Leaflet map, person + shelter markers"
```

---

### Task 2: Auto-Register Frontend Resource

**Files:**
- Modify: `custom_components/shelter_finder/__init__.py`
- Modify: `custom_components/shelter_finder/manifest.json`

- [ ] **Step 1: Add `frontend` to manifest dependencies**

In `custom_components/shelter_finder/manifest.json`, change:

```json
"dependencies": ["http", "webhook"]
```

to:

```json
"dependencies": ["http", "webhook", "frontend"]
```

- [ ] **Step 2: Add static path registration in __init__.py**

In `custom_components/shelter_finder/__init__.py`, add inside `async_setup_entry()`, after the webhook registration and before the platform forward:

```python
    # --- Register frontend static path ---
    should_register_static = not hass.data[DOMAIN].get("_static_registered")
    if should_register_static:
        hass.http.register_static_path(
            "/shelter_finder/shelter-map-card.js",
            hass.config.path("custom_components/shelter_finder/www/shelter-map-card.js"),
            cache_headers=True,
        )
        hass.data[DOMAIN]["_static_registered"] = True

        # Auto-register Lovelace resource (storage mode only)
        try:
            resources = hass.data.get("lovelace", {}).get("resources")
            if resources:
                url = "/shelter_finder/shelter-map-card.js"
                existing = [r for r in resources.async_items() if r.get("url") == url]
                if not existing:
                    await resources.async_create_item({"res_type": "module", "url": url})
        except Exception:
            _LOGGER.debug(
                "Lovelace is in YAML mode or resources unavailable. "
                "Add manually: resources: [{url: /shelter_finder/shelter-map-card.js, type: module}]"
            )
```

- [ ] **Step 3: Update the onboarding notification to mention the card**

The notification already says "Add the map card: Edit dashboard > + > Shelter Finder Map" — no change needed.

- [ ] **Step 4: Commit**

```bash
git add custom_components/shelter_finder/__init__.py custom_components/shelter_finder/manifest.json
git commit -m "feat: auto-register Lovelace resource for shelter map card"
```

---

### Task 3: Update README for v0.2

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Map Card section to README.md**

After the "## Entities" section, add:

```markdown
## Map Card

After installation, add the Shelter Finder map to your dashboard:

1. Edit your dashboard
2. Click **+** (Add Card)
3. Search for "Shelter Finder Map"
4. Configure the card:

```yaml
type: custom:shelter-map-card
title: Shelter Finder
entities:
  - person.alice
  - person.bob
default_zoom: 13
height: 400px
show_radius: true
```

The card shows:
- **Person markers** — colored circles with initials, positioned by GPS
- **Shelter markers** — icons by type (bunker, subway, school, etc.)
- **Popups** — click a person to see their nearest shelter, click a shelter for details
- **Alert banner** — red banner appears automatically when an alert is active

The map card resource is registered automatically — no YAML editing needed.
```

- [ ] **Step 2: Update version badge or mention v0.2 in Features section**

Add to the Features list:

```markdown
- **Interactive map** — Leaflet-based Lovelace card showing persons and shelters
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add map card documentation for v0.2"
```

---

### Task 4: Bump Version to 0.2.0

**Files:**
- Modify: `custom_components/shelter_finder/manifest.json`

- [ ] **Step 1: Update version in manifest.json**

Change `"version": "0.1.0"` to `"version": "0.2.0"`.

- [ ] **Step 2: Commit**

```bash
git add custom_components/shelter_finder/manifest.json
git commit -m "chore: bump version to 0.2.0"
```

---

## Review Checkpoint

After completing all 4 tasks:

1. Verify the JS file loads correctly (check syntax):
   ```bash
   node --check custom_components/shelter_finder/www/shelter-map-card.js || echo "Uses top-level await, needs --input-type=module"
   ```

2. Verify file structure:
   ```bash
   find custom_components/shelter_finder/www -type f
   ```

3. Push to GitHub.
