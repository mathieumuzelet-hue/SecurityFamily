"""Stub for homeassistant.components.sensor."""
from enum import Enum


class SensorStateClass(str, Enum):
    MEASUREMENT = "measurement"
    TOTAL = "total"
    TOTAL_INCREASING = "total_increasing"


class SensorEntity:
    _attr_has_entity_name = False
    _attr_unique_id = None
    _attr_name = None
    _attr_icon = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return self._attr_name

    @property
    def icon(self):
        return self._attr_icon

    @property
    def native_unit_of_measurement(self):
        return self._attr_native_unit_of_measurement

    @property
    def state_class(self):
        return self._attr_state_class

    @property
    def native_value(self):
        return None

    @property
    def extra_state_attributes(self):
        return {}
