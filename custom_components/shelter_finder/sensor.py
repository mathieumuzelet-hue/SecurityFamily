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
from .routing import calculate_eta_minutes, haversine_distance


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    persons = entry.data.get(CONF_PERSONS, [])

    entities = []
    for person_id in persons:
        person_name = person_id.split(".")[-1]
        entities.append(ShelterNearestSensor(coordinator, alert_coordinator, person_id, person_name))
        entities.append(ShelterDistanceSensor(coordinator, alert_coordinator, person_id, person_name))
        entities.append(ShelterETASensor(coordinator, alert_coordinator, person_id, person_name))
    entities.append(ShelterAlertTypeSensor(coordinator, alert_coordinator))
    async_add_entities(entities)


class ShelterNearestSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-home"

    def __init__(self, coordinator, alert_coordinator, person_id, person_name):
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_nearest"
        self._attr_name = f"{person_name} shelter nearest"

    @property
    def native_value(self):
        shelter = self._get_shelter()
        return shelter["name"] if shelter else None

    @property
    def extra_state_attributes(self):
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

    def _get_shelter(self):
        if self._alert_coordinator.is_active:
            return self._alert_coordinator.get_best_shelter(self._person_id)

        # In standby mode: find nearest shelter from cache
        if not self._coordinator.data:
            return None
        try:
            from homeassistant.core import HomeAssistant
            hass = self._coordinator.hass
            state = hass.states.get(self._person_id) if hass else None
            if state is None:
                return None
            lat = state.attributes.get("latitude")
            lon = state.attributes.get("longitude")
            if lat is None or lon is None:
                return None

            from .routing import haversine_distance
            nearest = None
            min_dist = float("inf")
            for shelter in self._coordinator.data:
                dist = haversine_distance(lat, lon, shelter["latitude"], shelter["longitude"])
                if dist < min_dist:
                    min_dist = dist
                    nearest = {**shelter, "distance_m": round(dist)}
            return nearest
        except Exception:
            return None


class ShelterDistanceSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, coordinator, alert_coordinator, person_id, person_name):
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_distance"
        self._attr_name = f"{person_name} shelter distance"

    @property
    def native_value(self):
        if self._alert_coordinator.is_active:
            shelter = self._alert_coordinator.get_best_shelter(self._person_id)
            return shelter["distance_m"] if shelter else None
        return self._nearest_distance()

    def _nearest_distance(self):
        if not self._coordinator.data:
            return None
        hass = self._coordinator.hass
        state = hass.states.get(self._person_id) if hass else None
        if state is None:
            return None
        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is None or lon is None:
            return None
        min_dist = float("inf")
        for shelter in self._coordinator.data:
            dist = haversine_distance(lat, lon, shelter["latitude"], shelter["longitude"])
            if dist < min_dist:
                min_dist = dist
        return round(min_dist) if min_dist < float("inf") else None


class ShelterETASensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:clock-fast"

    def __init__(self, coordinator, alert_coordinator, person_id, person_name):
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator
        self._person_id = person_id
        self._attr_unique_id = f"{DOMAIN}_{person_name}_eta"
        self._attr_name = f"{person_name} shelter ETA"

    @property
    def native_value(self):
        if self._alert_coordinator.is_active:
            shelter = self._alert_coordinator.get_best_shelter(self._person_id)
            return shelter.get("eta_minutes") if shelter else None
        return self._nearest_eta()

    def _nearest_eta(self):
        if not self._coordinator.data:
            return None
        hass = self._coordinator.hass
        state = hass.states.get(self._person_id) if hass else None
        if state is None:
            return None
        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is None or lon is None:
            return None
        min_dist = float("inf")
        for shelter in self._coordinator.data:
            dist = haversine_distance(lat, lon, shelter["latitude"], shelter["longitude"])
            if dist < min_dist:
                min_dist = dist
        if min_dist < float("inf"):
            return calculate_eta_minutes(round(min_dist), "walking")
        return None


class ShelterAlertTypeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_alert_type"
    _attr_name = "Alert type"
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator, alert_coordinator):
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    @property
    def native_value(self):
        if self._alert_coordinator.is_active and self._alert_coordinator.threat_type:
            return self._alert_coordinator.threat_type
        return "none"
