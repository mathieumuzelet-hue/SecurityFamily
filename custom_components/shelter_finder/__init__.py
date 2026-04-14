"""Shelter Finder integration."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import webhook as ha_webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .alert_coordinator import AlertCoordinator
from .cache import ShelterCache
from .const import (
    CONF_ADAPTIVE_RADIUS,
    CONF_ADAPTIVE_RADIUS_MAX,
    CONF_CACHE_TTL,
    CONF_CUSTOM_OSM_TAGS,
    CONF_DEFAULT_TRAVEL_MODE,
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_OSRM_ENABLED,
    CONF_OSRM_URL,
    CONF_OVERPASS_URL,
    CONF_PERSONS,
    CONF_RE_NOTIFICATION_INTERVAL,
    CONF_SEARCH_RADIUS,
    CONF_OSRM_TRANSPORT_MODE,
    CONF_WEBHOOK_ID,
    DEFAULT_ADAPTIVE_RADIUS_MAX,
    DEFAULT_CACHE_TTL,
    DEFAULT_MAX_RE_NOTIFICATIONS,
    DEFAULT_OSRM_ENABLED,
    DEFAULT_OSRM_URL,
    DEFAULT_OVERPASS_URL,
    DEFAULT_RADIUS,
    DEFAULT_RE_NOTIFICATION_INTERVAL,
    DEFAULT_OSRM_TRANSPORT_MODE,
    DEFAULT_TRAVEL_MODE,
    DOMAIN,
    SHELTER_TYPES,
    THREAT_TYPES,
)
from .coordinator import ShelterUpdateCoordinator
from .overpass import OverpassClient
from .routing import RoutingService
from .webhook import async_handle_webhook

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Shelter Finder domain."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def _register_frontend(hass: HomeAssistant) -> None:
    """Register the JS card as a Lovelace resource (once per HA instance)."""
    if hass.data.get(DOMAIN, {}).get("_frontend_registered"):
        return
    # Use the async API (HA 2024.7+)
    from homeassistant.components.http import StaticPathConfig
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/shelter_finder", str(Path(__file__).parent / "www"), False)]
    )
    from homeassistant.components.frontend import add_extra_js_url
    add_extra_js_url(hass, "/shelter_finder/shelter-map-card.js")
    hass.data.setdefault(DOMAIN, {})["_frontend_registered"] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelter Finder from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _register_frontend(hass)

    config = {**entry.data, **entry.options}
    persons = config.get(CONF_PERSONS, [])
    search_radius = config.get(CONF_SEARCH_RADIUS, DEFAULT_RADIUS)
    travel_mode = config.get(CONF_DEFAULT_TRAVEL_MODE, DEFAULT_TRAVEL_MODE)
    overpass_url = config.get(CONF_OVERPASS_URL, DEFAULT_OVERPASS_URL)
    cache_ttl = config.get(CONF_CACHE_TTL, DEFAULT_CACHE_TTL)
    adaptive_radius = config.get(CONF_ADAPTIVE_RADIUS, True)
    adaptive_radius_max = config.get(CONF_ADAPTIVE_RADIUS_MAX, DEFAULT_ADAPTIVE_RADIUS_MAX)
    re_notif_interval = config.get(CONF_RE_NOTIFICATION_INTERVAL, DEFAULT_RE_NOTIFICATION_INTERVAL)
    max_re_notif = config.get(CONF_MAX_RE_NOTIFICATIONS, DEFAULT_MAX_RE_NOTIFICATIONS)

    custom_tags_str = config.get(CONF_CUSTOM_OSM_TAGS, "")
    custom_tags = [t.strip() for t in custom_tags_str.split(",") if t.strip()] if custom_tags_str else None

    session = async_get_clientsession(hass)

    osrm_enabled = config.get(CONF_OSRM_ENABLED, DEFAULT_OSRM_ENABLED)
    osrm_url = config.get(CONF_OSRM_URL, DEFAULT_OSRM_URL)
    osrm_transport = config.get(CONF_OSRM_TRANSPORT_MODE, DEFAULT_OSRM_TRANSPORT_MODE)
    transport_mode = "driving" if osrm_transport == "driving" else "foot"
    routing_service = RoutingService(
        session=session,
        enabled=osrm_enabled,
        url=osrm_url,
        transport_mode=transport_mode,
    )

    storage_dir = Path(hass.config.path(".storage"))
    cache = ShelterCache(storage_dir, ttl_hours=cache_ttl)
    overpass_client = OverpassClient(session=session, url=overpass_url, tags=custom_tags)

    coordinator = ShelterUpdateCoordinator(
        hass=hass,
        cache=cache,
        overpass_client=overpass_client,
        persons=persons,
        search_radius=search_radius,
        adaptive_radius=adaptive_radius,
        adaptive_radius_max=adaptive_radius_max,
    )

    # First refresh — populates coordinator.data and sets up auto-polling
    await coordinator.async_config_entry_first_refresh()

    alert_coordinator = AlertCoordinator(
        hass=hass,
        shelter_coordinator=coordinator,
        persons=persons,
        travel_mode=travel_mode,
        re_notification_interval=re_notif_interval,
        max_re_notifications=max_re_notif,
        routing_service=routing_service,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "alert_coordinator": alert_coordinator,
        "cache": cache,
        "routing_service": routing_service,
    }
    hass.data[DOMAIN]["alert_coordinator"] = alert_coordinator

    if not hass.services.has_service(DOMAIN, "trigger_alert"):
        _register_services(hass)

    webhook_id = config.get(CONF_WEBHOOK_ID, entry.entry_id)
    try:
        ha_webhook.async_register(hass, DOMAIN, "Shelter Finder Alert", webhook_id, async_handle_webhook)
    except ValueError:
        _LOGGER.debug("Webhook %s already registered, skipping", webhook_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Onboarding notification
    shelter_count = len(coordinator.data) if coordinator.data else 0
    person_count = len(persons)
    from homeassistant.components.persistent_notification import async_create as pn_create
    pn_create(
        hass,
        (
            f"Shelter Finder installed!\n\n"
            f"- {person_count} person(s) tracked\n"
            f"- {shelter_count} shelter(s) found within {search_radius}m\n"
            f"- Webhook: `/api/webhook/{webhook_id}`\n\n"
            f"Add the map card: Edit dashboard > + > Shelter Finder Map\n"
            f"Test: Services > shelter_finder.trigger_alert"
        ),
        title="Shelter Finder",
        notification_id=f"{DOMAIN}_onboarding",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    config = {**entry.data, **entry.options}
    webhook_id = config.get(CONF_WEBHOOK_ID, entry.entry_id)
    ha_webhook.async_unregister(hass, webhook_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not any(k for k in hass.data[DOMAIN] if k != "alert_coordinator"):
            hass.data[DOMAIN].pop("alert_coordinator", None)

    return unload_ok


def _notify_coordinators(hass: HomeAssistant) -> None:
    """Signal all coordinators to re-push data to their entity listeners."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict) and "coordinator" in entry_data:
            coord = entry_data["coordinator"]
            coord.async_set_updated_data(coord.data or [])


def _register_services(hass: HomeAssistant) -> None:
    """Register Shelter Finder services."""

    async def handle_trigger_alert(call: ServiceCall) -> None:
        threat_type = call.data["threat_type"]
        message = call.data.get("message", "")
        drill = call.data.get("drill", False)
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.trigger(threat_type, triggered_by="service", drill=drill)
            _notify_coordinators(hass)
            await _send_alert_notifications(hass, ac, message)

    async def handle_cancel_alert(call: ServiceCall) -> None:
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.cancel()
            _notify_coordinators(hass)

    async def handle_refresh_shelters(call: ServiceCall) -> None:
        for entry_data in hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                await entry_data["coordinator"].async_force_refresh()

    async def handle_add_custom_poi(call: ServiceCall) -> None:
        name = call.data["name"]
        lat = call.data["latitude"]
        lon = call.data["longitude"]
        shelter_type = call.data["shelter_type"]
        notes = call.data.get("notes", "")

        for entry_data in hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "cache" in entry_data:
                cache = entry_data["cache"]
                pois = await hass.async_add_executor_job(cache.load_pois)
                pois.append({
                    "id": uuid.uuid4().hex,
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "shelter_type": shelter_type,
                    "notes": notes,
                    "source": "manual",
                })
                await hass.async_add_executor_job(cache.save_pois, pois)
                if "coordinator" in entry_data:
                    await entry_data["coordinator"].async_force_refresh()

    async def handle_confirm_safe(call: ServiceCall) -> None:
        person = call.data["person"]
        ac = hass.data.get(DOMAIN, {}).get("alert_coordinator")
        if ac:
            ac.confirm_safe(person)
            _notify_coordinators(hass)

    hass.services.async_register(
        DOMAIN, "trigger_alert", handle_trigger_alert,
        schema=vol.Schema({
            vol.Required("threat_type"): vol.In(THREAT_TYPES),
            vol.Optional("message", default=""): cv.string,
            vol.Optional("drill", default=False): cv.boolean,
        }),
    )
    hass.services.async_register(DOMAIN, "cancel_alert", handle_cancel_alert)
    hass.services.async_register(DOMAIN, "refresh_shelters", handle_refresh_shelters)
    hass.services.async_register(
        DOMAIN, "add_custom_poi", handle_add_custom_poi,
        schema=vol.Schema({
            vol.Required("name"): cv.string,
            vol.Required("latitude"): vol.Coerce(float),
            vol.Required("longitude"): vol.Coerce(float),
            vol.Required("shelter_type"): vol.In(SHELTER_TYPES),
            vol.Optional("notes", default=""): cv.string,
        }),
    )
    hass.services.async_register(
        DOMAIN, "confirm_safe", handle_confirm_safe,
        schema=vol.Schema({vol.Required("person"): cv.string}),
    )


def _find_mobile_app_service(hass: HomeAssistant, person_name: str) -> str | None:
    """Find the notify service for a person by checking available services."""
    # Try exact match first
    candidate = f"mobile_app_{person_name}"
    if hass.services.has_service("notify", candidate):
        return candidate

    # Try lowercase variants and partial matches
    for service in hass.services.async_services().get("notify", {}):
        if person_name.lower() in service.lower():
            return service

    return None


async def _send_alert_notifications(hass: HomeAssistant, alert_coordinator: AlertCoordinator, message: str = "") -> None:
    """Send push notifications to all tracked persons."""
    for person_id in alert_coordinator.persons:
        best = await alert_coordinator.get_best_shelter(person_id)
        if best is None:
            continue

        person_name = person_id.split(".")[-1]
        device_service = _find_mobile_app_service(hass, person_name)

        nav_url = (
            f"https://www.google.com/maps/dir/?api=1"
            f"&destination={best['latitude']},{best['longitude']}"
            f"&travelmode=walking"
        )

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
