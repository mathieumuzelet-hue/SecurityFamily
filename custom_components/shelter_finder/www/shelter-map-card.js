// Shelter Finder Map Card — Lovelace custom card
// Loaded as ES module from /shelter_finder/shelter-map-card.js

const LitModule = await (async () => {
  try {
    return await import("/frontend_latest/lit.js");
  } catch {
    return await import("https://cdn.jsdelivr.net/npm/lit@3/+esm");
  }
})();

const { LitElement, html, css, nothing } = LitModule;

const LEAFLET_CSS_URL = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS_URL = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet-src.esm.js";

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

const PERSON_COLORS = ["#3182ce", "#e53e3e", "#38a169", "#d69e2e", "#805ad5", "#dd6b20", "#319795", "#b83280"];

function createPersonIcon(L, name, colorIndex) {
  const color = PERSON_COLORS[colorIndex % PERSON_COLORS.length];
  const initial = (name || "?")[0].toUpperCase();
  return L.divIcon({
    className: "shelter-person-marker",
    html: '<div style="background:' + color + ';color:white;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3)">' + initial + "</div>",
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
}

function createShelterIcon(L, shelterType) {
  const colors = {
    bunker: "#e53e3e", subway: "#3182ce", civic: "#38a169", school: "#d69e2e",
    worship: "#805ad5", shelter: "#718096", sports: "#dd6b20", hospital: "#e53e3e",
    government: "#2d3748", open_space: "#48bb78",
  };
  const color = colors[shelterType] || colors.shelter;
  return L.divIcon({
    className: "shelter-poi-marker",
    html: '<div style="background:' + color + ';color:white;width:24px;height:24px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:14px;border:1px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.3);opacity:0.85">&#9978;</div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14],
  });
}

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
    this._map = this._L.map(container, { zoomControl: true, attributionControl: true });

    this._L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(this._map);

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

      const prev = prevHass?.states[entityId];
      if (prev && prev.attributes.latitude === latitude && prev.attributes.longitude === longitude) {
        return;
      }

      if (this._personMarkers.has(entityId)) {
        this._personMarkers.get(entityId).setLatLng(latlng);
      } else {
        const name = friendly_name || entityId.split(".").pop();
        const icon = createPersonIcon(L, name, index);
        const marker = L.marker(latlng, { icon, title: name, zIndexOffset: 1000 })
          .bindPopup("<b>" + name + "</b>")
          .addTo(this._map);
        this._personMarkers.set(entityId, marker);
      }

      const name = friendly_name || entityId.split(".").pop();
      const personKey = entityId.split(".").pop();
      const nearestSensor = "sensor.shelter_finder_" + personKey + "_nearest";
      const distSensor = "sensor.shelter_finder_" + personKey + "_distance";
      const nearestState = hass.states[nearestSensor];
      const distState = hass.states[distSensor];

      let popupHtml = "<b>" + name + "</b>";
      if (nearestState && nearestState.state !== "unknown" && nearestState.state !== "unavailable") {
        popupHtml += "<br>Nearest: " + nearestState.state;
        if (distState && distState.state !== "unknown") {
          popupHtml += " (" + distState.state + "m)";
        }
      }
      const marker = this._personMarkers.get(entityId);
      if (marker) marker.getPopup()?.setContent(popupHtml);
    });

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
    const shelterEntities = Object.keys(hass.states).filter(
      (id) => id.startsWith("sensor.shelter_finder_") && id.endsWith("_nearest")
    );

    const seenIds = new Set();

    for (const sensorId of shelterEntities) {
      const state = hass.states[sensorId];
      if (!state || state.state === "unknown" || state.state === "unavailable") continue;

      const { latitude, longitude, shelter_type, source } = state.attributes;
      if (latitude == null || longitude == null) continue;

      const markerId = latitude + "," + longitude;
      if (seenIds.has(markerId)) continue;
      seenIds.add(markerId);

      if (!this._shelterMarkers.has(markerId)) {
        const icon = createShelterIcon(L, shelter_type || "shelter");
        const marker = L.marker([latitude, longitude], { icon })
          .bindPopup("<b>" + state.state + "</b><br>Type: " + (shelter_type || "unknown") + "<br>Source: " + (source || "osm"))
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
      ${isAlert ? html`<div class="alert-banner">ALERTE: ${alertType?.toUpperCase() || "UNKNOWN"}</div>` : nothing}
      <ha-card header=${this.config?.title ?? "Shelter Finder"}>
        <div id="map" style="height:${this.config?.height ?? "400px"}"></div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; }
      #map { width: 100%; border-radius: 0 0 var(--ha-card-border-radius, 12px) var(--ha-card-border-radius, 12px); }
      .alert-banner {
        background: #e53e3e; color: white; text-align: center; padding: 8px;
        font-weight: bold; font-size: 14px; letter-spacing: 1px;
        border-radius: var(--ha-card-border-radius, 12px) var(--ha-card-border-radius, 12px) 0 0;
      }
      .shelter-person-marker, .shelter-poi-marker { background: transparent !important; border: none !important; }
    `;
  }

  getCardSize() { return 5; }

  static getConfigElement() {
    return document.createElement("shelter-map-card-editor");
  }

  static getStubConfig() {
    return { title: "Shelter Finder", entities: ["person.alice"], default_zoom: 13 };
  }
}

class ShelterMapCardEditor extends LitElement {
  static get properties() {
    return { hass: {}, _config: { state: true } };
  }

  setConfig(config) { this._config = config; }

  _valueChanged(ev) {
    const cfg = { ...this._config, [ev.target.name]: ev.target.value };
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg } }));
  }

  render() {
    if (!this._config) return nothing;
    return html`
      <div class="editor">
        <label>Title <input name="title" .value=${this._config.title ?? ""} @change=${this._valueChanged}></label>
        <label>Entities (comma-separated)
          <input name="_entities_raw" .value=${(this._config.entities ?? []).join(", ")}
            @change=${(ev) => {
              const cfg = { ...this._config, entities: ev.target.value.split(",").map((s) => s.trim()).filter(Boolean) };
              this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg } }));
            }}>
        </label>
        <label>Default zoom <input type="number" name="default_zoom" .value=${this._config.default_zoom ?? 13} @change=${this._valueChanged}></label>
        <label>Height <input name="height" .value=${this._config.height ?? "400px"} @change=${this._valueChanged}></label>
      </div>
    `;
  }

  static get styles() {
    return css`
      .editor { display: flex; flex-direction: column; gap: 8px; padding: 16px; }
      label { display: flex; flex-direction: column; font-size: 0.85em; }
      input { margin-top: 4px; padding: 6px 8px; border: 1px solid var(--divider-color, #ccc); border-radius: 4px; }
    `;
  }
}

customElements.define("shelter-map-card-editor", ShelterMapCardEditor);
customElements.define("shelter-map-card", ShelterMapCard);

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
