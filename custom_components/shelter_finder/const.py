"""Constants for Shelter Finder."""

from __future__ import annotations

DOMAIN = "shelter_finder"

# ---------------------------------------------------------------------------
# Core config keys
# ---------------------------------------------------------------------------
CONF_PERSONS = "persons"
CONF_SEARCH_RADIUS = "search_radius"
CONF_LANGUAGE = "language"
CONF_ENABLED_THREATS = "enabled_threats"
CONF_DEFAULT_TRAVEL_MODE = "default_travel_mode"
CONF_OVERPASS_URL = "overpass_url"
CONF_CACHE_TTL = "cache_ttl"
CONF_CUSTOM_OSM_TAGS = "custom_osm_tags"
CONF_WEBHOOK_ID = "webhook_id"
CONF_RE_NOTIFICATION_INTERVAL = "re_notification_interval"
CONF_MAX_RE_NOTIFICATIONS = "max_re_notifications"
CONF_ADAPTIVE_RADIUS = "adaptive_radius"
CONF_ADAPTIVE_RADIUS_MAX = "adaptive_radius_max"

# Defaults
DEFAULT_RADIUS = 2000
DEFAULT_LANGUAGE = "fr"
DEFAULT_TRAVEL_MODE = "walking"
DEFAULT_OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"
DEFAULT_CACHE_TTL = 24  # hours
DEFAULT_RE_NOTIFICATION_INTERVAL = 5  # minutes
DEFAULT_MAX_RE_NOTIFICATIONS = 3
DEFAULT_ADAPTIVE_RADIUS_MAX = 15000  # meters
ADAPTIVE_RADIUS_MIN_RESULTS = 3

# Threat types.
# Note: "attack" and "armed_conflict" are deliberately not mapped by any
# FR-Alert provider — no public government source currently exposes those
# categories. They remain available for manual / webhook / button triggers.
THREAT_TYPES = [
    "storm",
    "earthquake",
    "attack",
    "armed_conflict",
    "flood",
    "nuclear_chemical",
]

# Shelter types
SHELTER_TYPES = [
    "subway",
    "bunker",
    "civic",
    "school",
    "worship",
    "shelter",
    "sports",
    "hospital",
    "government",
    "open_space",
]

# Threat → shelter scoring matrix
THREAT_SHELTER_SCORES: dict[str, dict[str, int]] = {
    "storm": {"subway": 10, "bunker": 9, "civic": 8, "school": 7, "worship": 6, "shelter": 5, "sports": 4, "hospital": 3, "government": 3, "open_space": 1},
    "earthquake": {"open_space": 10, "sports": 7, "shelter": 5, "school": 4, "subway": 2, "bunker": 2, "civic": 3, "worship": 3, "hospital": 4, "government": 3},
    "attack": {"bunker": 10, "subway": 9, "civic": 7, "worship": 6, "school": 5, "hospital": 4, "government": 6, "shelter": 3, "sports": 2, "open_space": 1},
    "armed_conflict": {"bunker": 10, "subway": 10, "civic": 6, "school": 5, "hospital": 4, "government": 5, "worship": 4, "shelter": 3, "sports": 2, "open_space": 1},
    "flood": {"civic": 8, "school": 7, "worship": 6, "sports": 5, "hospital": 7, "government": 7, "shelter": 4, "open_space": 3, "subway": 1, "bunker": 1},
    "nuclear_chemical": {"bunker": 10, "subway": 8, "civic": 4, "government": 4, "hospital": 3, "school": 3, "worship": 2, "shelter": 1, "sports": 1, "open_space": 0},
}

# Default OSM tags for Overpass queries
DEFAULT_OSM_TAGS = [
    "amenity=shelter",
    "building=bunker",
    "amenity=place_of_worship",
    "railway=station",
    "station=subway",
    "building=civic",
    "building=government",
    "building=school",
    "amenity=school",
    "building=hospital",
    "leisure=sports_centre",
]

# OSM tag → shelter type mapping
OSM_TAG_TO_SHELTER_TYPE: dict[str, str] = {
    "amenity=shelter": "shelter",
    "building=bunker": "bunker",
    "amenity=place_of_worship": "worship",
    "railway=station": "subway",
    "station=subway": "subway",
    "building=civic": "civic",
    "building=government": "government",
    "building=school": "school",
    "amenity=school": "school",
    "building=hospital": "hospital",
    "leisure=sports_centre": "sports",
}

# Travel modes
TRAVEL_MODES = ["walking", "driving"]

# Walking/driving speed estimates (m/s) for ETA calculation
TRAVEL_SPEEDS = {
    "walking": 1.4,   # ~5 km/h
    "driving": 8.3,   # ~30 km/h (urban average)
}

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
SEVERITY_RANK: dict[str, int] = {level: idx for idx, level in enumerate(SEVERITY_LEVELS)}

# ---------------------------------------------------------------------------
# v0.6 — OSRM routing (Routage)
# ---------------------------------------------------------------------------
CONF_OSRM_ENABLED = "osrm_enabled"
CONF_OSRM_URL = "osrm_url"
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

# TTS defaults
DEFAULT_TTS_VOLUME = 0.8  # 0.0-1.0, applied to media_player before speaking
DEFAULT_TTS_BUFFER_SECONDS = 2  # extra seconds after estimated duration

# Auto-detection order: first match wins (service name only, domain is "tts").
TTS_SERVICE_CANDIDATES: list[str] = [
    "google_translate_say",
    "cloud_say",
    "speak",
]

# ---------------------------------------------------------------------------
# v0.6 — Drill mode (service parameter, scaffolded here for shared use)
# ---------------------------------------------------------------------------
CONF_DRILL = "drill"
DEFAULT_DRILL = False

# French labels for threat types (used in voice announcements and UI;
# ASCII-only to maximize TTS engine compatibility — no accents).
THREAT_LABELS_FR: dict[str, str] = {
    "storm": "tempete",
    "earthquake": "seisme",
    "attack": "attaque",
    "armed_conflict": "conflit arme",
    "flood": "inondation",
    "nuclear_chemical": "nucleaire chimique",
}
