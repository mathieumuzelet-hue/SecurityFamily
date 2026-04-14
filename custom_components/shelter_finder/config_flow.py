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
    CONF_CACHE_TTL,
    CONF_CUSTOM_OSM_TAGS,
    CONF_DEFAULT_TRAVEL_MODE,
    CONF_ENABLED_THREATS,
    CONF_LANGUAGE,
    CONF_MAX_RE_NOTIFICATIONS,
    CONF_OSRM_ENABLED,
    CONF_OSRM_MODE,
    CONF_OSRM_TRANSPORT_MODE,
    CONF_OSRM_URL,
    CONF_OVERPASS_URL,
    CONF_PERSONS,
    CONF_PROVIDER_ALERT_RADIUS_KM,
    CONF_PROVIDER_AUTO_CANCEL,
    CONF_PROVIDER_GEORISQUES,
    CONF_PROVIDER_METEO_FRANCE,
    CONF_PROVIDER_MIN_SEVERITY,
    CONF_PROVIDER_POLL_INTERVAL,
    CONF_RE_NOTIFICATION_INTERVAL,
    CONF_SEARCH_RADIUS,
    CONF_TTS_ENABLED,
    CONF_TTS_MEDIA_PLAYERS,
    CONF_TTS_SERVICE,
    CONF_TTS_VOLUME,
    CONF_WEBHOOK_ID,
    DEFAULT_CACHE_TTL,
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_RE_NOTIFICATIONS,
    DEFAULT_OSRM_ENABLED,
    DEFAULT_OSRM_MODE,
    DEFAULT_OSRM_TRANSPORT_MODE,
    DEFAULT_OSRM_URL,
    DEFAULT_OVERPASS_URL,
    DEFAULT_PROVIDER_ALERT_RADIUS_KM,
    DEFAULT_PROVIDER_AUTO_CANCEL,
    DEFAULT_PROVIDER_GEORISQUES,
    DEFAULT_PROVIDER_METEO_FRANCE,
    DEFAULT_PROVIDER_MIN_SEVERITY,
    DEFAULT_PROVIDER_POLL_INTERVAL,
    DEFAULT_RADIUS,
    DEFAULT_RE_NOTIFICATION_INTERVAL,
    DEFAULT_TRAVEL_MODE,
    DEFAULT_TTS_ENABLED,
    DEFAULT_TTS_MEDIA_PLAYERS,
    DEFAULT_TTS_SERVICE,
    DEFAULT_TTS_VOLUME,
    DOMAIN,
    OSRM_MODES,
    OSRM_TRANSPORT_MODES,
    PROVIDER_POLL_INTERVAL_MAX,
    PROVIDER_POLL_INTERVAL_MIN,
    SEVERITY_LEVELS,
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
    """Multi-step options flow for Shelter Finder v0.6.

    Steps:
      1. init           -> Sources & Rayon
      2. routing        -> Routage (OSRM)
      3. notifications  -> Notifications (re-notif + TTS)
      4. advanced       -> Avance (overpass_url, custom_osm_tags)
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        self._options: dict[str, Any] = {}

    # ------------------------------------------------------------------ utils
    def _current(self) -> dict[str, Any]:
        """Return merged view of existing options over data (options wins)."""
        merged: dict[str, Any] = {}
        merged.update(self._config_entry.data or {})
        merged.update(self._config_entry.options or {})
        return merged

    # ---------------------------------------------------------------- step 1
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1 — Sources & Rayon."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_routing()

        cur = self._current()

        schema = vol.Schema({
            vol.Required(
                CONF_SEARCH_RADIUS,
                default=cur.get(CONF_SEARCH_RADIUS, DEFAULT_RADIUS),
            ): vol.All(int, vol.Range(min=500, max=50000)),
            vol.Required(
                CONF_ADAPTIVE_RADIUS,
                default=cur.get(CONF_ADAPTIVE_RADIUS, True),
            ): bool,
            vol.Required(
                CONF_CACHE_TTL,
                default=cur.get(CONF_CACHE_TTL, DEFAULT_CACHE_TTL),
            ): vol.All(int, vol.Range(min=1, max=168)),
            vol.Required(
                CONF_PROVIDER_GEORISQUES,
                default=cur.get(CONF_PROVIDER_GEORISQUES, DEFAULT_PROVIDER_GEORISQUES),
            ): bool,
            vol.Required(
                CONF_PROVIDER_METEO_FRANCE,
                default=cur.get(CONF_PROVIDER_METEO_FRANCE, DEFAULT_PROVIDER_METEO_FRANCE),
            ): bool,
            vol.Required(
                CONF_PROVIDER_POLL_INTERVAL,
                default=cur.get(CONF_PROVIDER_POLL_INTERVAL, DEFAULT_PROVIDER_POLL_INTERVAL),
            ): vol.All(int, vol.Range(min=PROVIDER_POLL_INTERVAL_MIN, max=PROVIDER_POLL_INTERVAL_MAX)),
            vol.Required(
                CONF_PROVIDER_MIN_SEVERITY,
                default=cur.get(CONF_PROVIDER_MIN_SEVERITY, DEFAULT_PROVIDER_MIN_SEVERITY),
            ): vol.In(SEVERITY_LEVELS),
            vol.Required(
                CONF_PROVIDER_AUTO_CANCEL,
                default=cur.get(CONF_PROVIDER_AUTO_CANCEL, DEFAULT_PROVIDER_AUTO_CANCEL),
            ): bool,
            vol.Required(
                CONF_PROVIDER_ALERT_RADIUS_KM,
                default=cur.get(CONF_PROVIDER_ALERT_RADIUS_KM, DEFAULT_PROVIDER_ALERT_RADIUS_KM),
            ): vol.All(int, vol.Range(min=1, max=200)),
        })

        return self.async_show_form(step_id="init", data_schema=schema)

    # ---------------------------------------------------------------- step 2
    async def async_step_routing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2 — Routage (OSRM)."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_notifications()

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_OSRM_ENABLED,
                default=cur.get(CONF_OSRM_ENABLED, DEFAULT_OSRM_ENABLED),
            ): bool,
            vol.Required(
                CONF_OSRM_MODE,
                default=cur.get(CONF_OSRM_MODE, DEFAULT_OSRM_MODE),
            ): vol.In(OSRM_MODES),
            vol.Required(
                CONF_OSRM_URL,
                default=cur.get(CONF_OSRM_URL, DEFAULT_OSRM_URL),
            ): str,
            vol.Required(
                CONF_OSRM_TRANSPORT_MODE,
                default=cur.get(CONF_OSRM_TRANSPORT_MODE, DEFAULT_OSRM_TRANSPORT_MODE),
            ): vol.In(OSRM_TRANSPORT_MODES),
        })
        return self.async_show_form(step_id="routing", data_schema=schema)

    # ---------------------------------------------------------------- step 3
    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3 — Notifications (re-notif + TTS)."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_advanced()

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_RE_NOTIFICATION_INTERVAL,
                default=cur.get(CONF_RE_NOTIFICATION_INTERVAL, DEFAULT_RE_NOTIFICATION_INTERVAL),
            ): vol.All(int, vol.Range(min=1, max=60)),
            vol.Required(
                CONF_MAX_RE_NOTIFICATIONS,
                default=cur.get(CONF_MAX_RE_NOTIFICATIONS, DEFAULT_MAX_RE_NOTIFICATIONS),
            ): vol.All(int, vol.Range(min=0, max=20)),
            vol.Required(
                CONF_TTS_ENABLED,
                default=cur.get(CONF_TTS_ENABLED, DEFAULT_TTS_ENABLED),
            ): bool,
            vol.Required(
                CONF_TTS_SERVICE,
                default=cur.get(CONF_TTS_SERVICE, DEFAULT_TTS_SERVICE),
            ): str,
            vol.Required(
                CONF_TTS_MEDIA_PLAYERS,
                default=cur.get(CONF_TTS_MEDIA_PLAYERS, DEFAULT_TTS_MEDIA_PLAYERS),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[],
                    multiple=True,
                    custom_value=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_TTS_VOLUME,
                default=cur.get(CONF_TTS_VOLUME, DEFAULT_TTS_VOLUME),
            ): vol.All(int, vol.Range(min=0, max=100)),
        })
        return self.async_show_form(step_id="notifications", data_schema=schema)

    # ---------------------------------------------------------------- step 4
    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4 — Avance (placeholder, filled in Task 10)."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        cur = self._current()
        schema = vol.Schema({
            vol.Required(
                CONF_OVERPASS_URL,
                default=cur.get(CONF_OVERPASS_URL, DEFAULT_OVERPASS_URL),
            ): str,
        })
        return self.async_show_form(step_id="advanced", data_schema=schema)
