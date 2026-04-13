"""Config flow for Shelter Finder."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ADAPTIVE_RADIUS,
    CONF_ADAPTIVE_RADIUS_MAX,
    CONF_CACHE_TTL,
    CONF_CUSTOM_OSM_TAGS,
    CONF_DEFAULT_TRAVEL_MODE,
    CONF_ENABLED_THREATS,
    CONF_LANGUAGE,
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_OSRM_ENABLED,
    CONF_OSRM_URL,
    CONF_OVERPASS_URL,
    CONF_PERSONS,
    CONF_RE_NOTIFICATION_INTERVAL,
    CONF_SEARCH_RADIUS,
    CONF_WEBHOOK_ID,
    DEFAULT_ADAPTIVE_RADIUS_MAX,
    DEFAULT_CACHE_TTL,
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_RE_NOTIFICATIONS,
    DEFAULT_OVERPASS_URL,
    DEFAULT_RADIUS,
    DEFAULT_RE_NOTIFICATION_INTERVAL,
    DEFAULT_TRAVEL_MODE,
    DOMAIN,
    THREAT_TYPES,
    TRAVEL_MODES,
)


class ShelterFinderConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._user_input.update(user_input)
            return await self.async_step_threats()

        person_entities = [state.entity_id for state in self.hass.states.async_all("person")]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PERSONS, default=person_entities): SelectSelector(
                    SelectSelectorConfig(
                        options=person_entities,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_SEARCH_RADIUS, default=DEFAULT_RADIUS): vol.All(int, vol.Range(min=500, max=50000)),
                vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(["fr", "en"]),
            }),
        )

    async def async_step_threats(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._user_input.update(user_input)
            self._user_input[CONF_WEBHOOK_ID] = f"sf_{uuid.uuid4().hex[:12]}"
            return self.async_create_entry(title="Shelter Finder", data=self._user_input)

        return self.async_show_form(
            step_id="threats",
            data_schema=vol.Schema({
                vol.Required(CONF_ENABLED_THREATS, default=THREAT_TYPES): SelectSelector(
                    SelectSelectorConfig(
                        options=THREAT_TYPES,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_DEFAULT_TRAVEL_MODE, default=DEFAULT_TRAVEL_MODE): SelectSelector(
                    SelectSelectorConfig(
                        options=TRAVEL_MODES,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ShelterFinderOptionsFlow(config_entry)


class ShelterFinderOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options or self._config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_SEARCH_RADIUS, default=current.get(CONF_SEARCH_RADIUS, DEFAULT_RADIUS)): int,
                vol.Required(CONF_DEFAULT_TRAVEL_MODE, default=current.get(CONF_DEFAULT_TRAVEL_MODE, DEFAULT_TRAVEL_MODE)): vol.In(TRAVEL_MODES),
                vol.Required(CONF_OVERPASS_URL, default=current.get(CONF_OVERPASS_URL, DEFAULT_OVERPASS_URL)): str,
                vol.Required(CONF_CACHE_TTL, default=current.get(CONF_CACHE_TTL, DEFAULT_CACHE_TTL)): int,
                vol.Required(CONF_ADAPTIVE_RADIUS, default=current.get(CONF_ADAPTIVE_RADIUS, True)): bool,
                vol.Required(CONF_RE_NOTIFICATION_INTERVAL, default=current.get(CONF_RE_NOTIFICATION_INTERVAL, DEFAULT_RE_NOTIFICATION_INTERVAL)): int,
                vol.Required(CONF_MAX_RE_NOTIFICATIONS, default=current.get(CONF_MAX_RE_NOTIFICATIONS, DEFAULT_MAX_RE_NOTIFICATIONS)): int,
            }),
        )
