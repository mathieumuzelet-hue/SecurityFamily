"""Tests for TTSService."""

from __future__ import annotations

from custom_components.shelter_finder.const import (
    DEFAULT_TTS_BUFFER_SECONDS,
    DEFAULT_TTS_VOLUME,
    THREAT_LABELS_FR,
    THREAT_TYPES,
    TTS_SERVICE_CANDIDATES,
)


def test_threat_labels_fr_covers_all_threat_types() -> None:
    for threat in THREAT_TYPES:
        assert threat in THREAT_LABELS_FR, f"Missing French label for {threat}"


def test_threat_labels_fr_values() -> None:
    assert THREAT_LABELS_FR["storm"] == "tempete"
    assert THREAT_LABELS_FR["earthquake"] == "seisme"
    assert THREAT_LABELS_FR["attack"] == "attaque"
    assert THREAT_LABELS_FR["armed_conflict"] == "conflit arme"
    assert THREAT_LABELS_FR["flood"] == "inondation"
    assert THREAT_LABELS_FR["nuclear_chemical"] == "nucleaire chimique"


def test_default_tts_volume_is_80_percent() -> None:
    assert DEFAULT_TTS_VOLUME == 0.8


def test_default_tts_buffer_seconds_is_2() -> None:
    assert DEFAULT_TTS_BUFFER_SECONDS == 2


def test_tts_service_candidates_order() -> None:
    assert TTS_SERVICE_CANDIDATES == [
        "google_translate_say",
        "cloud_say",
        "speak",
    ]


from custom_components.shelter_finder.tts_service import build_message


def test_build_message_real_alert() -> None:
    msg = build_message(
        threat_type="storm",
        shelter_name="Ecole Jules Ferry",
        distance_m=320,
        eta_minutes=4,
        is_drill=False,
    )
    assert msg == (
        "Alerte tempete. Dirigez-vous vers Ecole Jules Ferry, "
        "a 320 metres, environ 4 minutes a pied."
    )


def test_build_message_drill_has_prefix() -> None:
    msg = build_message(
        threat_type="attack",
        shelter_name="Metro Republique",
        distance_m=150,
        eta_minutes=2,
        is_drill=True,
    )
    assert msg.startswith("Ceci est un exercice. ")
    assert "Alerte attaque." in msg
    assert "Metro Republique" in msg


def test_build_message_unknown_threat_falls_back_to_raw_key() -> None:
    msg = build_message(
        threat_type="unknown_threat",
        shelter_name="Abri",
        distance_m=100,
        eta_minutes=1,
        is_drill=False,
    )
    assert "Alerte unknown_threat." in msg


def test_build_message_unknown_eta_shows_question_mark() -> None:
    msg = build_message(
        threat_type="flood",
        shelter_name="Mairie",
        distance_m=500,
        eta_minutes=None,
        is_drill=False,
    )
    assert "environ ? minutes a pied." in msg


from unittest.mock import MagicMock

from custom_components.shelter_finder.tts_service import resolve_tts_service


def _hass_with_tts_services(names: list[str]) -> MagicMock:
    hass = MagicMock()
    hass.services.async_services.return_value = {
        "tts": {n: MagicMock() for n in names},
        "notify": {"mobile_app_alice": MagicMock()},
    }
    return hass


def test_resolve_tts_service_uses_configured_when_available() -> None:
    hass = _hass_with_tts_services(["google_translate_say", "cloud_say"])
    assert resolve_tts_service(hass, configured="cloud_say") == "cloud_say"


def test_resolve_tts_service_falls_back_when_configured_missing() -> None:
    hass = _hass_with_tts_services(["google_translate_say"])
    # Configured "piper" is not available -> fall back to auto-detect.
    assert resolve_tts_service(hass, configured="piper") == "google_translate_say"


def test_resolve_tts_service_auto_detect_prefers_google() -> None:
    hass = _hass_with_tts_services(["cloud_say", "google_translate_say", "speak"])
    assert resolve_tts_service(hass, configured=None) == "google_translate_say"


def test_resolve_tts_service_auto_detect_second_choice() -> None:
    hass = _hass_with_tts_services(["cloud_say", "speak"])
    assert resolve_tts_service(hass, configured=None) == "cloud_say"


def test_resolve_tts_service_auto_detect_third_choice() -> None:
    hass = _hass_with_tts_services(["speak"])
    assert resolve_tts_service(hass, configured=None) == "speak"


def test_resolve_tts_service_none_available_returns_none() -> None:
    hass = MagicMock()
    hass.services.async_services.return_value = {"notify": {}}
    assert resolve_tts_service(hass, configured=None) is None


def test_resolve_tts_service_empty_string_treated_as_none() -> None:
    hass = _hass_with_tts_services(["google_translate_say"])
    assert resolve_tts_service(hass, configured="") == "google_translate_say"
