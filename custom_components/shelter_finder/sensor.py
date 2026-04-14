"""Sensor platform for Shelter Finder."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .alert_coordinator import AlertCoordinator
from .const import CONF_PERSONS, DOMAIN
from .coordinator import ShelterUpdateCoordinator
from .routing import RoutingService, calculate_eta_minutes, haversine_distance


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    persons = entry.data.get(CONF_PERSONS, [])

    entities: list[SensorEntity] = []
    for person_id in persons:
        person_name = person_id.split(".")[-1]
        entities.append(ShelterNearestSensor(coordinator, alert_coordinator, person_id, person_name))
        entities.append(ShelterDistanceSensor(coordinator, alert_coordinator, person_id, person_name))
        entities.append(ShelterETASensor(coordinator, alert_coordinator, person_id, person_name))
    entities.append(ShelterAlertTypeSensor(coordinator, alert_coordinator))
    async_add_entities(entities)


def _find_nearest_shelter(
    shelters: list[dict[str, Any]], lat: float, lon: float,
) -> dict[str, Any] | None:
    nearest = None
    min_dist = float("inf")
    for shelter in shelters:
        dist = haversine_distance(lat, lon, shelter["latitude"], shelter["longitude"])
        if dist < min_dist:
            min_dist = dist
            nearest = {**shelter, "distance_m": round(dist)}
    return nearest


async def _async_find_nearest_shelter(
    routing_service: RoutingService | None,
    shelters: list[dict[str, Any]],
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    if not shelters:
        return None
    # Ensure ids
    normalized = []
    for s in shelters:
        if "id" not in s:
            s = {**s, "id": f"{s.get('latitude')}_{s.get('longitude')}"}
        normalized.append(s)

    if routing_service is None:
        best = None
        best_dist = float("inf")
        for s in normalized:
            d = haversine_distance(lat, lon, s["latitude"], s["longitude"])
            if d < best_dist:
                best_dist = d
                best = {**s, "distance_m": round(d), "route_source": "haversine",
                        "eta_minutes": calculate_eta_minutes(d, "walking")}
        return best

    routes = await routing_service.async_get_routes_batch(lat, lon, normalized, top_n=10)
    best = None
    best_dist = float("inf")
    for s in normalized:
        r = routes.get(s["id"])
        if r is None:
            continue
        if r.distance_m < best_dist:
            best_dist = r.distance_m
            best = {
                **s,
                "distance_m": round(r.distance_m),
                "eta_minutes": round(r.eta_seconds / 60.0, 1),
                "route_source": r.source,
            }
    return best


def _get_person_coords(hass: HomeAssistant, person_id: str) -> tuple[float, float] | None:
    state = hass.states.get(person_id)
    if state is None:
        return None
    lat = state.attributes.get("latitude")
    lon = state.attributes.get("longitude")
    if lat is None or lon is None:
        return None
    return (lat, lon)


class ShelterNearestSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-home"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator, person_id: str, person_name: str) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_nearest"
        self._attr_name = f"{person_name} shelter nearest"

    @property
    def native_value(self) -> str | None:
        shelter = self._get_shelter()
        return shelter["name"] if shelter else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        shelter = self._get_shelter()
        if shelter is None:
            return {}
        return {
            "latitude": shelter.get("latitude"),
            "longitude": shelter.get("longitude"),
            "shelter_type": shelter.get("shelter_type"),
            "source": shelter.get("source"),
            "distance_m": shelter.get("distance_m"),
            "score": shelter.get("score"),
        }

    def _get_shelter(self) -> dict[str, Any] | None:
        if self._alert_coordinator.is_active:
            return self._alert_coordinator.get_best_shelter(self._person_id)
        shelters = self.coordinator.data or []
        if not shelters:
            return None
        coords = _get_person_coords(self.hass, self._person_id)
        if coords is None:
            return None
        return _find_nearest_shelter(shelters, coords[0], coords[1])


class ShelterDistanceSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator, person_id: str, person_name: str) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_distance"
        self._attr_name = f"{person_name} shelter distance"

    @property
    def native_value(self) -> int | None:
        if self._alert_coordinator.is_active:
            shelter = self._alert_coordinator.get_best_shelter(self._person_id)
            return shelter["distance_m"] if shelter else None
        shelters = self.coordinator.data or []
        if not shelters:
            return None
        coords = _get_person_coords(self.hass, self._person_id)
        if coords is None:
            return None
        nearest = _find_nearest_shelter(shelters, coords[0], coords[1])
        return nearest["distance_m"] if nearest else None


class ShelterETASensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:clock-fast"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator, person_id: str, person_name: str) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_eta"
        self._attr_name = f"{person_name} shelter ETA"

    @property
    def native_value(self) -> float | None:
        if self._alert_coordinator.is_active:
            shelter = self._alert_coordinator.get_best_shelter(self._person_id)
            return shelter.get("eta_minutes") if shelter else None
        shelters = self.coordinator.data or []
        if not shelters:
            return None
        coords = _get_person_coords(self.hass, self._person_id)
        if coords is None:
            return None
        nearest = _find_nearest_shelter(shelters, coords[0], coords[1])
        if nearest:
            return calculate_eta_minutes(nearest["distance_m"], "walking")
        return None


class ShelterAlertTypeSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_alert_type"
    _attr_name = "Alert type"
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        super().__init__(coordinator)
        self._alert_coordinator = alert_coordinator

    @property
    def native_value(self) -> str:
        if self._alert_coordinator.is_active and self._alert_coordinator.threat_type:
            return self._alert_coordinator.threat_type
        return "none"
