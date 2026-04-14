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
