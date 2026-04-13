"""Constants for Shelter Finder."""

from __future__ import annotations

DOMAIN = "shelter_finder"

# Config keys
CONF_PERSONS = "persons"
CONF_SEARCH_RADIUS = "search_radius"
CONF_LANGUAGE = "language"
CONF_ENABLED_THREATS = "enabled_threats"
CONF_DEFAULT_TRAVEL_MODE = "default_travel_mode"
CONF_OVERPASS_URL = "overpass_url"
CONF_CACHE_TTL = "cache_ttl"
CONF_OSRM_ENABLED = "osrm_enabled"
CONF_OSRM_URL = "osrm_url"
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

# Threat types
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
