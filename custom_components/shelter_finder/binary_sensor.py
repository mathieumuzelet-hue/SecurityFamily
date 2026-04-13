"""Binary sensor platform for Shelter Finder."""

from __future__ import annotations
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .alert_coordinator import AlertCoordinator
from .const import DOMAIN
from .coordinator import ShelterUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    async_add_entities([ShelterAlertBinarySensor(coordinator, alert_coordinator)])


class ShelterAlertBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_alert"
    _attr_name = "Alert"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator, alert_coordinator):
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    @property
    def is_on(self):
        return self._alert_coordinator.is_active

    @property
    def extra_state_attributes(self):
        ac = self._alert_coordinator
        # Include all shelters from cache for the map card
        shelters = self._coordinator.data or []
        shelter_list = [
            {"name": s.get("name", ""), "lat": s.get("latitude"), "lon": s.get("longitude"),
             "type": s.get("shelter_type", ""), "source": s.get("source", "osm")}
            for s in shelters if s.get("latitude") and s.get("longitude")
        ]
        return {
            "threat_type": ac.threat_type,
            "triggered_at": str(ac.triggered_at) if ac.triggered_at else None,
            "triggered_by": ac.triggered_by,
            "persons_safe": ac.persons_safe,
            "shelters": shelter_list,
            "shelter_count": len(shelter_list),
        }
