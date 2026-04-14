"""Ensure v0.6 config keys are defined in const.py."""

from __future__ import annotations

import custom_components.shelter_finder.const as const


def test_v06_conf_keys_exist() -> None:
    # Sources & Rayon
    assert const.CONF_PROVIDER_GEORISQUES == "provider_georisques"
    assert const.CONF_PROVIDER_METEO_FRANCE == "provider_meteo_france"
    assert const.CONF_PROVIDER_POLL_INTERVAL == "provider_poll_interval"
    assert const.CONF_PROVIDER_MIN_SEVERITY == "provider_min_severity"
    assert const.CONF_PROVIDER_AUTO_CANCEL == "provider_auto_cancel"
    assert const.CONF_PROVIDER_ALERT_RADIUS_KM == "provider_alert_radius_km"
    # Routage
    assert const.CONF_OSRM_ENABLED == "osrm_enabled"
    assert const.CONF_OSRM_MODE == "osrm_mode"
    assert const.CONF_OSRM_URL == "osrm_url"
    assert const.CONF_OSRM_TRANSPORT_MODE == "osrm_transport_mode"
    # Notifications
    assert const.CONF_TTS_ENABLED == "tts_enabled"
    assert const.CONF_TTS_SERVICE == "tts_service"
    assert const.CONF_TTS_MEDIA_PLAYERS == "tts_media_players"
    assert const.CONF_TTS_VOLUME == "tts_volume"
    # Drill (service param, but scaffold constant)
    assert const.CONF_DRILL == "drill"


def test_v06_defaults_exist() -> None:
    assert const.DEFAULT_PROVIDER_POLL_INTERVAL == 60
    assert const.DEFAULT_PROVIDER_MIN_SEVERITY == "severe"
    assert const.DEFAULT_PROVIDER_AUTO_CANCEL is True
    assert const.DEFAULT_OSRM_URL == "https://router.project-osrm.org"
    assert const.DEFAULT_OSRM_MODE == "public"
    assert const.DEFAULT_OSRM_TRANSPORT_MODE == "walking"
    assert const.DEFAULT_TTS_VOLUME == 0.8
    assert const.SEVERITY_LEVELS == ["minor", "moderate", "severe", "extreme"]
    assert const.OSRM_MODES == ["public", "self_hosted"]
    assert const.THREAT_LABELS_FR["storm"] == "tempete"
    assert const.THREAT_LABELS_FR["nuclear_chemical"] == "nucleaire chimique"
