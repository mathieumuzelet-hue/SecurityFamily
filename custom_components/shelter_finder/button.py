"""Button platform for Shelter Finder."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .alert_coordinator import AlertCoordinator
from .const import DOMAIN, THREAT_TYPES
from .coordinator import ShelterUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    alert_coordinator = data["alert_coordinator"]
    entities: list[ButtonEntity] = [
        ShelterTriggerAlertButton(coordinator, alert_coordinator),
        ShelterCancelAlertButton(coordinator, alert_coordinator),
        # One drill button per threat type — lets users rehearse every
        # response plan (storm, earthquake, attack, armed_conflict, flood,
        # nuclear_chemical). The default "storm" button keeps the legacy
        # entity_id for backwards compatibility.
        ShelterDrillButton(coordinator, alert_coordinator),
    ]
    for threat in THREAT_TYPES:
        if threat == "storm":
            continue  # covered by the legacy default ShelterDrillButton
        entities.append(ShelterDrillButton(coordinator, alert_coordinator, threat_type=threat))
    async_add_entities(entities)


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
    """Drill button for a specific threat type.

    Default is "storm" for backwards compatibility with the pre-v0.6.5 single
    button. Pass `threat_type` to create drill buttons for other threats —
    one button per THREAT_TYPES entry is spawned from async_setup_entry.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:school-outline"

    def __init__(
        self,
        coordinator: ShelterUpdateCoordinator,
        alert_coordinator: AlertCoordinator,
        threat_type: str = "storm",
    ) -> None:
        self._coordinator = coordinator
        self._alert_coordinator = alert_coordinator
        self._threat_type = threat_type
        if threat_type == "storm":
            # Keep legacy unique_id so existing installs don't get a duplicate.
            self._attr_unique_id = f"{DOMAIN}_drill_alert"
            self._attr_name = "Drill alert (exercice)"
        else:
            self._attr_unique_id = f"{DOMAIN}_drill_alert_{threat_type}"
            self._attr_name = f"Drill alert {threat_type} (exercice)"

    async def async_press(self) -> None:
        self._alert_coordinator.trigger(
            self._threat_type, triggered_by="button", drill=True,
        )
        self._coordinator.async_set_updated_data(self._coordinator.data or [])
