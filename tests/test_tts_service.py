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


from custom_components.shelter_finder.tts_service import resolve_targets


def _state(entity_id: str, state: str) -> MagicMock:
    s = MagicMock()
    s.entity_id = entity_id
    s.state = state
    return s


def test_resolve_targets_uses_configured_list() -> None:
    hass = MagicMock()
    configured = ["media_player.kitchen", "media_player.living_room"]
    assert resolve_targets(hass, configured) == configured


def test_resolve_targets_empty_config_scans_available_on_or_idle() -> None:
    hass = MagicMock()
    hass.states.async_all.return_value = [
        _state("media_player.kitchen", "on"),
        _state("media_player.bedroom", "idle"),
        _state("media_player.garage", "off"),
        _state("media_player.tv", "unavailable"),
        _state("light.hall", "on"),  # not a media_player
    ]
    assert resolve_targets(hass, []) == [
        "media_player.kitchen",
        "media_player.bedroom",
    ]


def test_resolve_targets_none_config_treated_as_empty() -> None:
    hass = MagicMock()
    hass.states.async_all.return_value = [_state("media_player.kitchen", "on")]
    assert resolve_targets(hass, None) == ["media_player.kitchen"]


def test_resolve_targets_no_available_returns_empty() -> None:
    hass = MagicMock()
    hass.states.async_all.return_value = [_state("media_player.tv", "off")]
    assert resolve_targets(hass, []) == []


from custom_components.shelter_finder.tts_service import estimate_duration_seconds


def test_estimate_duration_short_message_floor() -> None:
    # Short messages have a 3s floor.
    assert estimate_duration_seconds("Hi.") == 3


def test_estimate_duration_long_message_scales() -> None:
    # 150 chars / 15 cps = 10s
    msg = "x" * 150
    assert estimate_duration_seconds(msg) == 10


def test_estimate_duration_rounds_up() -> None:
    # 16 chars / 15 cps = 1.07 -> floor kicks in -> 3s
    assert estimate_duration_seconds("x" * 16) == 3


def test_estimate_duration_medium_message() -> None:
    # 75 chars / 15 cps = 5s
    assert estimate_duration_seconds("x" * 75) == 5


import pytest

from custom_components.shelter_finder.tts_service import TTSService


@pytest.mark.asyncio
async def test_tts_service_disabled_is_noop() -> None:
    hass = MagicMock()
    hass.services.async_call = MagicMock()  # would be AsyncMock if called
    svc = TTSService(
        hass=hass,
        enabled=False,
        configured_service=None,
        configured_players=[],
        volume=0.8,
    )
    await svc.async_announce(
        threat_type="storm",
        shelters_by_person={"person.alice": {"name": "Abri", "distance_m": 100, "eta_minutes": 1}},
        is_drill=False,
    )
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_tts_service_no_resolved_service_is_noop(caplog) -> None:
    hass = MagicMock()
    hass.services.async_services.return_value = {"tts": {}}  # none registered
    hass.services.async_call = MagicMock()
    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service=None,
        configured_players=["media_player.kitchen"],
        volume=0.8,
    )
    with caplog.at_level("WARNING"):
        await svc.async_announce(
            threat_type="storm",
            shelters_by_person={"person.alice": {"name": "Abri", "distance_m": 100, "eta_minutes": 1}},
            is_drill=False,
        )
    hass.services.async_call.assert_not_called()
    assert any("No TTS service available" in r.message for r in caplog.records)


from unittest.mock import AsyncMock, call


def _speaker_state(entity_id: str, volume_level: float | None, state: str = "idle") -> MagicMock:
    s = MagicMock()
    s.entity_id = entity_id
    s.state = state
    s.attributes = {} if volume_level is None else {"volume_level": volume_level}
    return s


def _hass_for_announce(targets_states: list[MagicMock], tts_services: list[str]) -> MagicMock:
    hass = MagicMock()
    hass.services.async_services.return_value = {
        "tts": {n: MagicMock() for n in tts_services},
    }
    hass.services.async_call = AsyncMock()
    # states.get(entity_id) returns matching state
    by_id = {s.entity_id: s for s in targets_states}
    hass.states.get = lambda eid: by_id.get(eid)
    hass.states.async_all = MagicMock(return_value=targets_states)
    return hass


@pytest.mark.asyncio
async def test_tts_service_full_flow_real_alert(monkeypatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(
        "custom_components.shelter_finder.tts_service.asyncio.sleep", fake_sleep
    )

    kitchen = _speaker_state("media_player.kitchen", 0.25)
    bedroom = _speaker_state("media_player.bedroom", 0.4)
    hass = _hass_for_announce([kitchen, bedroom], ["google_translate_say"])

    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service=None,
        configured_players=["media_player.kitchen", "media_player.bedroom"],
        volume=0.8,
    )

    await svc.async_announce(
        threat_type="storm",
        shelters_by_person={
            "person.alice": {"name": "Ecole", "distance_m": 300, "eta_minutes": 4},
        },
        is_drill=False,
    )

    calls = hass.services.async_call.await_args_list

    # 1. Set volume 0.8 on both speakers
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.kitchen", "volume_level": 0.8},
        blocking=True,
    ) in calls
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.bedroom", "volume_level": 0.8},
        blocking=True,
    ) in calls

    # 2. tts.google_translate_say on both
    expected_message = (
        "Alerte tempete. Dirigez-vous vers Ecole, a 300 metres, "
        "environ 4 minutes a pied."
    )
    assert call(
        "tts", "google_translate_say",
        {"entity_id": "media_player.kitchen", "message": expected_message},
        blocking=False,
    ) in calls
    assert call(
        "tts", "google_translate_say",
        {"entity_id": "media_player.bedroom", "message": expected_message},
        blocking=False,
    ) in calls

    # 3. One sleep for estimated duration + 2s buffer
    assert len(sleeps) == 1
    assert sleeps[0] == estimate_duration_seconds(expected_message) + 2

    # 4. Restore volumes
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.kitchen", "volume_level": 0.25},
        blocking=True,
    ) in calls
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.bedroom", "volume_level": 0.4},
        blocking=True,
    ) in calls


@pytest.mark.asyncio
async def test_tts_service_drill_prefix(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.shelter_finder.tts_service.asyncio.sleep",
        AsyncMock(),
    )
    kitchen = _speaker_state("media_player.kitchen", 0.3)
    hass = _hass_for_announce([kitchen], ["speak"])
    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service="speak",
        configured_players=["media_player.kitchen"],
        volume=0.8,
    )
    await svc.async_announce(
        threat_type="attack",
        shelters_by_person={"person.alice": {"name": "Metro", "distance_m": 100, "eta_minutes": 2}},
        is_drill=True,
    )
    # Find the tts.speak call and check message starts with drill prefix
    tts_calls = [
        c for c in hass.services.async_call.await_args_list
        if c.args[:2] == ("tts", "speak")
    ]
    assert len(tts_calls) == 1
    assert tts_calls[0].args[2]["message"].startswith("Ceci est un exercice. ")


@pytest.mark.asyncio
async def test_tts_service_restores_volume_even_if_speak_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.shelter_finder.tts_service.asyncio.sleep",
        AsyncMock(),
    )
    kitchen = _speaker_state("media_player.kitchen", 0.2)
    hass = _hass_for_announce([kitchen], ["google_translate_say"])

    # Make tts.google_translate_say raise; volume_set must still succeed.
    async def side_effect(domain, service, data, blocking=False):
        if domain == "tts":
            raise RuntimeError("TTS engine unreachable")
        return None

    hass.services.async_call = AsyncMock(side_effect=side_effect)

    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service=None,
        configured_players=["media_player.kitchen"],
        volume=0.8,
    )
    await svc.async_announce(
        threat_type="storm",
        shelters_by_person={"person.alice": {"name": "Abri", "distance_m": 200, "eta_minutes": 3}},
        is_drill=False,
    )

    calls = hass.services.async_call.await_args_list
    assert call(
        "media_player", "volume_set",
        {"entity_id": "media_player.kitchen", "volume_level": 0.2},
        blocking=True,
    ) in calls


@pytest.mark.asyncio
async def test_tts_service_missing_volume_level_skips_restore(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.shelter_finder.tts_service.asyncio.sleep",
        AsyncMock(),
    )
    no_vol = _speaker_state("media_player.weird", volume_level=None)
    hass = _hass_for_announce([no_vol], ["google_translate_say"])
    svc = TTSService(
        hass=hass,
        enabled=True,
        configured_service=None,
        configured_players=["media_player.weird"],
        volume=0.8,
    )
    await svc.async_announce(
        threat_type="storm",
        shelters_by_person={"person.alice": {"name": "Abri", "distance_m": 100, "eta_minutes": 1}},
        is_drill=False,
    )
    # Only one volume_set (the alert-level one); no restore since we had no baseline.
    vol_set_calls = [
        c for c in hass.services.async_call.await_args_list
        if c.args[:2] == ("media_player", "volume_set")
    ]
    assert len(vol_set_calls) == 1
    assert vol_set_calls[0].args[2]["volume_level"] == 0.8


from custom_components.shelter_finder.tts_service import build_shelters_by_person


async def test_build_shelters_by_person_skips_none() -> None:
    ac = MagicMock()
    ac.persons = ["person.alice", "person.bob"]

    async def _get(p):
        if p == "person.alice":
            return {"name": "Abri", "distance_m": 200, "eta_minutes": 3}
        return None

    ac.get_best_shelter = _get
    result = await build_shelters_by_person(ac)
    assert result == {
        "person.alice": {"name": "Abri", "distance_m": 200, "eta_minutes": 3},
    }


async def test_build_shelters_by_person_empty_when_no_shelters() -> None:
    ac = MagicMock()
    ac.persons = ["person.alice"]

    async def _none(_p):
        return None

    ac.get_best_shelter = _none
    assert await build_shelters_by_person(ac) == {}
