// Shelter Finder Map Card — Lovelace custom card
// Vanilla HTMLElement approach — no Lit dependency

const LEAFLET_CSS_URL = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS_URL = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js";
const PERSON_COLORS = ["#3182ce", "#e53e3e", "#38a169", "#d69e2e", "#805ad5", "#dd6b20", "#319795", "#b83280"];

function _loadLeafletScript() {
  return new Promise(function(resolve, reject) {
    if (window.L) { resolve(window.L); return; }
    var script = document.createElement("script");
    script.src = LEAFLET_JS_URL;
    script.onload = function() { resolve(window.L); };
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

function createPersonIcon(L, name, colorIndex) {
  var color = PERSON_COLORS[colorIndex % PERSON_COLORS.length];
  var initial = (name || "?")[0].toUpperCase();
  return L.divIcon({
    className: "shelter-person-marker",
    html: '<div style="background:' + color + ';color:white;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3)">' + initial + '</div>',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
}

function createShelterIcon(L, shelterType) {
  var colors = {
    bunker: "#e53e3e", subway: "#3182ce", civic: "#38a169", school: "#d69e2e",
    worship: "#805ad5", shelter: "#718096", sports: "#dd6b20", hospital: "#e53e3e",
    government: "#2d3748", open_space: "#48bb78",
  };
  var color = colors[shelterType] || colors.shelter;
  return L.divIcon({
    className: "shelter-poi-marker",
    html: '<div style="background:' + color + ';color:white;width:24px;height:24px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:12px;border:1px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.3);opacity:0.85">S</div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14],
  });
}

class ShelterMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._map = null;
    this._L = null;
    this._personMarkers = new Map();
    this._shelterMarkers = new Map();
    this._fitted = false;
    this._mapReady = false;
  }

  setConfig(config) {
    if (!config.entities || !config.entities.length) {
      throw new Error("shelter-map-card: define at least one entity in 'entities'");
    }
    this.config = Object.assign({
      title: "Shelter Finder",
      default_zoom: 13,
      alert_zoom: 15,
      height: "400px",
    }, config);

    this._render();
  }

  set hass(hass) {
    var old = this._hass;
    this._hass = hass;
    if (this._map && this._L) {
      this._updatePersonMarkers(hass, old);
      this._updateShelterMarkers(hass);
    }
    this._updateAlertBanner();
  }

  _render() {
    var root = this.shadowRoot;
    root.textContent = "";

    // Style
    var style = document.createElement("style");
    style.textContent = [
      ":host { display: block; }",
      "#map { width: 100%; border-radius: 0 0 12px 12px; }",
      ".alert-banner { background: #e53e3e; color: white; text-align: center; padding: 8px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 12px 12px 0 0; display: none; }",
      ".alert-banner.active { display: block; }",
      ".shelter-person-marker, .shelter-poi-marker { background: transparent !important; border: none !important; }",
      "ha-card { overflow: hidden; }",
    ].join("\n");
    root.appendChild(style);

    // Leaflet CSS
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = LEAFLET_CSS_URL;
    root.appendChild(link);

    // Alert banner
    var banner = document.createElement("div");
    banner.className = "alert-banner";
    banner.id = "alert-banner";
    root.appendChild(banner);

    // HA Card
    var card = document.createElement("ha-card");
    card.header = this.config.title;

    var mapDiv = document.createElement("div");
    mapDiv.id = "map";
    mapDiv.style.height = this.config.height;
    card.appendChild(mapDiv);
    root.appendChild(card);

    // Init map after DOM is ready
    var self = this;
    setTimeout(function() { self._initMap(); }, 100);
  }

  async _initMap() {
    try {
      this._L = await _loadLeafletScript();
    } catch (e) {
      console.error("SHELTER-MAP-CARD: Failed to load Leaflet", e);
      return;
    }

    var container = this.shadowRoot.querySelector("#map");
    if (!container) return;

    this._map = this._L.map(container, { zoomControl: true, attributionControl: true });

    this._L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
      referrerPolicy: "origin",
    }).addTo(this._map);

    this._mapReady = true;

    if (this._hass) {
      this._updatePersonMarkers(this._hass, null);
      this._updateShelterMarkers(this._hass);
    }
  }

  _findEntityId(hass, suffix) {
    // Find entity_id ending with suffix, trying common patterns
    var keys = Object.keys(hass.states);
    for (var i = 0; i < keys.length; i++) {
      if (keys[i].endsWith(suffix)) return keys[i];
    }
    return null;
  }

  _updateAlertBanner() {
    var banner = this.shadowRoot ? this.shadowRoot.querySelector("#alert-banner") : null;
    if (!banner || !this._hass) return;
    var alertId = this._findEntityId(this._hass, "_alert") || "binary_sensor.alert";
    var alertSensor = this._hass.states[alertId];
    var isAlert = alertSensor && alertSensor.state === "on";
    var alertTypeId = this._findEntityId(this._hass, "_alert_type") || "sensor.alert_type";
    var alertType = this._hass.states[alertTypeId];
    if (isAlert) {
      banner.textContent = "ALERTE: " + ((alertType ? alertType.state : "UNKNOWN").toUpperCase());
      banner.classList.add("active");
    } else {
      banner.classList.remove("active");
    }
  }

  _updatePersonMarkers(hass, prevHass) {
    var L = this._L;
    if (!L || !this._map) return;
    var entities = this.config.entities || [];
    var bounds = [];
    var self = this;

    entities.forEach(function(entityId, index) {
      var stateObj = hass.states[entityId];
      if (!stateObj) return;

      var lat = stateObj.attributes.latitude;
      var lon = stateObj.attributes.longitude;
      var friendly_name = stateObj.attributes.friendly_name;
      if (lat == null || lon == null) return;

      var latlng = [lat, lon];
      bounds.push(latlng);

      var prev = prevHass ? prevHass.states[entityId] : null;
      if (prev && prev.attributes.latitude === lat && prev.attributes.longitude === lon) {
        return;
      }

      var name = friendly_name || entityId.split(".").pop();

      if (self._personMarkers.has(entityId)) {
        self._personMarkers.get(entityId).setLatLng(latlng);
      } else {
        var icon = createPersonIcon(L, name, index);
        var marker = L.marker(latlng, { icon: icon, title: name, zIndexOffset: 1000 })
          .bindPopup("<b>" + name + "</b>")
          .addTo(self._map);
        self._personMarkers.set(entityId, marker);
      }

      // Update popup with shelter info — find sensors by suffix pattern
      var personKey = entityId.split(".").pop();
      var nearestState = hass.states["sensor." + personKey + "_shelter_nearest"]
        || hass.states["sensor.shelter_finder_" + personKey + "_nearest"];
      var distState = hass.states["sensor." + personKey + "_shelter_distance"]
        || hass.states["sensor.shelter_finder_" + personKey + "_distance"];

      var popupHtml = "<b>" + name + "</b>";
      if (nearestState && nearestState.state !== "unknown" && nearestState.state !== "unavailable") {
        popupHtml += "<br>Abri: " + nearestState.state;
        if (distState && distState.state !== "unknown" && distState.state !== "unavailable") {
          popupHtml += " (" + distState.state + "m)";
        }
      }
      var mk = self._personMarkers.get(entityId);
      if (mk && mk.getPopup()) mk.getPopup().setContent(popupHtml);
    });

    if (!self._fitted && bounds.length) {
      self._fitted = true;
      if (bounds.length === 1) {
        self._map.setView(bounds[0], Number(self.config.default_zoom));
      } else {
        self._map.fitBounds(bounds, { padding: [40, 40] });
      }
    }
  }

  _updateShelterMarkers(hass) {
    var L = this._L;
    if (!L || !this._map) return;
    var self = this;

    // Find the alert binary sensor (which contains all shelters in attributes)
    var alertId = this._findEntityId(hass, "_alert");
    if (!alertId) {
      // Fallback: try common names
      alertId = "binary_sensor.alert";
    }
    var alertState = hass.states[alertId];
    if (!alertState || !alertState.attributes || !alertState.attributes.shelters) return;

    var shelters = alertState.attributes.shelters;
    var seenIds = new Set();

    for (var i = 0; i < shelters.length; i++) {
      var s = shelters[i];
      if (s.lat == null || s.lon == null) continue;

      var markerId = s.lat + "," + s.lon;
      if (seenIds.has(markerId)) continue;
      seenIds.add(markerId);

      if (!self._shelterMarkers.has(markerId)) {
        var icon = createShelterIcon(L, s.type || "shelter");
        var marker = L.marker([s.lat, s.lon], { icon: icon })
          .bindPopup("<b>" + (s.name || "Abri") + "</b><br>Type: " + (s.type || "?") + "<br>Source: " + (s.source || "osm"))
          .addTo(self._map);
        self._shelterMarkers.set(markerId, marker);
      }
    }
  }

  getCardSize() { return 5; }
}

customElements.define("shelter-map-card", ShelterMapCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "shelter-map-card",
  name: "Shelter Finder Map",
  description: "Carte des abris et membres du foyer",
  preview: false,
});

console.info(
  "%c SHELTER-MAP-CARD %c v0.2.0 ",
  "background:#3182ce;color:white;font-weight:bold;padding:2px 6px;border-radius:3px 0 0 3px",
  "background:#e2e8f0;padding:2px 6px;border-radius:0 3px 3px 0"
);
