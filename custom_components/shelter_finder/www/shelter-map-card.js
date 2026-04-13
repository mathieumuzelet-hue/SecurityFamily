// Shelter Finder Map Card — Lovelace custom card
// Vanilla HTMLElement approach — no Lit dependency

const LEAFLET_CSS_URL = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS_URL = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js";
const PERSON_COLORS = ["#3182ce", "#e53e3e", "#38a169", "#d69e2e", "#805ad5", "#dd6b20", "#319795", "#b83280"];
const SHELTER_COLORS = {
  bunker: "#e53e3e", subway: "#3182ce", civic: "#38a169", school: "#d69e2e",
  worship: "#805ad5", shelter: "#718096", sports: "#dd6b20", hospital: "#e53e3e",
  government: "#2d3748", open_space: "#48bb78",
};
const SHELTER_LABELS = {
  bunker: "B", subway: "M", civic: "C", school: "E", worship: "W",
  shelter: "S", sports: "G", hospital: "H", government: "G", open_space: "O",
};

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

function _haversine(lat1, lon1, lat2, lon2) {
  var R = 6371000;
  var dLat = (lat2 - lat1) * Math.PI / 180;
  var dLon = (lon2 - lon1) * Math.PI / 180;
  var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
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
  var color = SHELTER_COLORS[shelterType] || SHELTER_COLORS.shelter;
  var label = SHELTER_LABELS[shelterType] || "S";
  return L.divIcon({
    className: "shelter-poi-marker",
    html: '<div style="background:' + color + ';color:white;width:24px;height:24px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold;border:1px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.3);opacity:0.9">' + label + '</div>',
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
    this._buildDOM();
  }

  set hass(hass) {
    var old = this._hass;
    this._hass = hass;
    if (this._map && this._L) {
      this._updatePersonMarkers(hass, old);
      this._updateShelterMarkers(hass);
      this._updateAlertBanner(hass);
    }
  }

  _buildDOM() {
    var root = this.shadowRoot;
    root.textContent = "";

    var style = document.createElement("style");
    style.textContent =
      ":host { display: block; }" +
      "#map { width: 100%; border-radius: 0 0 12px 12px; }" +
      ".alert-banner { background: #e53e3e; color: white; text-align: center; padding: 8px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 12px 12px 0 0; display: none; }" +
      ".alert-banner.active { display: block; }" +
      ".shelter-person-marker, .shelter-poi-marker { background: transparent !important; border: none !important; }" +
      "ha-card { overflow: hidden; }";
    root.appendChild(style);

    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = LEAFLET_CSS_URL;
    root.appendChild(link);

    var banner = document.createElement("div");
    banner.className = "alert-banner";
    banner.id = "alert-banner";
    root.appendChild(banner);

    var card = document.createElement("ha-card");
    card.header = this.config.title;
    var mapDiv = document.createElement("div");
    mapDiv.id = "map";
    mapDiv.style.height = this.config.height;
    card.appendChild(mapDiv);
    root.appendChild(card);

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

    if (this._hass) {
      this._updatePersonMarkers(this._hass, null);
      this._updateShelterMarkers(this._hass);
      this._updateAlertBanner(this._hass);
    }
  }

  _getPersonPositions(hass) {
    var positions = [];
    var entities = this.config.entities || [];
    for (var i = 0; i < entities.length; i++) {
      var s = hass.states[entities[i]];
      if (s && s.attributes.latitude != null && s.attributes.longitude != null) {
        positions.push({ id: entities[i], lat: s.attributes.latitude, lon: s.attributes.longitude, name: s.attributes.friendly_name || entities[i].split(".").pop() });
      }
    }
    return positions;
  }

  _updateAlertBanner(hass) {
    var banner = this.shadowRoot ? this.shadowRoot.querySelector("#alert-banner") : null;
    if (!banner) return;
    var alertSensor = hass.states["binary_sensor.shelter_finder_alert"];
    var isAlert = alertSensor && alertSensor.state === "on";
    if (isAlert) {
      var alertType = hass.states["sensor.shelter_finder_alert_type"];
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

      // Update popup with nearest shelter info
      var personKey = entityId.split(".").pop();
      var nearestState = hass.states["sensor.shelter_finder_" + personKey + "_nearest"];
      var distState = hass.states["sensor.shelter_finder_" + personKey + "_distance"];

      var popupHtml = "<b>" + name + "</b>";
      if (nearestState && nearestState.state && nearestState.state !== "unknown" && nearestState.state !== "unavailable") {
        popupHtml += "<br>Abri: " + nearestState.state;
        if (distState && distState.state && distState.state !== "unknown") {
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

    // Read all shelters from binary_sensor.alert attributes
    var alertState = hass.states["binary_sensor.alert"];
    if (!alertState || !alertState.attributes || !alertState.attributes.shelters) return;

    var shelters = alertState.attributes.shelters;
    var persons = this._getPersonPositions(hass);
    var seenIds = new Set();

    for (var i = 0; i < shelters.length; i++) {
      var s = shelters[i];
      if (s.lat == null || s.lon == null) continue;

      var markerId = s.lat.toFixed(6) + "," + s.lon.toFixed(6);
      if (seenIds.has(markerId)) continue;
      seenIds.add(markerId);

      if (!this._shelterMarkers.has(markerId)) {
        var icon = createShelterIcon(L, s.type || "shelter");

        // Build popup with distances to each person
        var popupHtml = "<b>" + (s.name || "Abri") + "</b><br>Type: " + (s.type || "?");
        for (var j = 0; j < persons.length; j++) {
          var dist = Math.round(_haversine(persons[j].lat, persons[j].lon, s.lat, s.lon));
          var eta = Math.round(dist / 1.4 / 60); // walking speed ~5km/h
          popupHtml += "<br>" + persons[j].name + ": " + dist + "m (~" + eta + " min)";
        }

        var marker = L.marker([s.lat, s.lon], { icon: icon })
          .bindPopup(popupHtml)
          .addTo(this._map);
        this._shelterMarkers.set(markerId, marker);
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
  "%c SHELTER-MAP-CARD %c v0.2.1 ",
  "background:#3182ce;color:white;font-weight:bold;padding:2px 6px;border-radius:3px 0 0 3px",
  "background:#e2e8f0;padding:2px 6px;border-radius:0 3px 3px 0"
);
