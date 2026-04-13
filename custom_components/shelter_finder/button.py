"""Button platform for Shelter Finder."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .alert_coordinator import AlertCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    alert_coordinator = hass.data[DOMAIN][entry.entry_id]["alert_coordinator"]
    async_add_entities([
        ShelterTriggerAlertButton(alert_coordinator),
        ShelterCancelAlertButton(alert_coordinator),
    ])


class ShelterTriggerAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_trigger_alert"
    _attr_name = "Trigger alert"
    _attr_icon = "mdi:alert-plus"

    def __init__(self, alert_coordinator):
        self._alert_coordinator = alert_coordinator

    async def async_press(self):
        self._alert_coordinator.trigger("storm", triggered_by="button")


class ShelterCancelAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_cancel_alert"
    _attr_name = "Cancel alert"
    _attr_icon = "mdi:alert-remove"

    def __init__(self, alert_coordinator):
        self._alert_coordinator = alert_coordinator

    async def async_press(self):
        self._alert_coordinator.cancel()
