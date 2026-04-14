"""Button platform for Shelter Finder."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities([
        ShelterTriggerAlertButton(coordinator, alert_coordinator),
        ShelterCancelAlertButton(coordinator, alert_coordinator),
        ShelterDrillButton(coordinator, alert_coordinator),
    ])


class ShelterTriggerAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_trigger_alert"
    _attr_name = "Trigger alert"
    _attr_icon = "mdi:alert-plus"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        self._alert_coordinator.trigger("storm", triggered_by="button")
        self._coordinator.async_set_updated_data(self._coordinator.data or [])


class ShelterCancelAlertButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_cancel_alert"
    _attr_name = "Cancel alert"
    _attr_icon = "mdi:alert-remove"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        self._alert_coordinator.cancel()
        self._coordinator.async_set_updated_data(self._coordinator.data or [])


class ShelterDrillButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_drill_alert"
    _attr_name = "Drill alert (exercice)"
    _attr_icon = "mdi:school-outline"

    def __init__(self, coordinator: ShelterUpdateCoordinator, alert_coordinator: AlertCoordinator) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator

    async def async_press(self) -> None:
        self._alert_coordinator.trigger("storm", triggered_by="button", drill=True)
        self._coordinator.async_set_updated_data(self._coordinator.data or [])
