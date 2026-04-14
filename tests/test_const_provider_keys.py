"""Constants regression test for FR-Alert provider config keys."""
from custom_components.shelter_finder import const


def test_provider_conf_keys_present():
    assert const.CONF_PROVIDER_GEORISQUES == "provider_georisques"
    assert const.CONF_PROVIDER_METEO_FRANCE == "provider_meteo_france"
    assert const.CONF_PROVIDER_POLL_INTERVAL == "provider_poll_interval"
    assert const.CONF_PROVIDER_ALERT_RADIUS_KM == "provider_alert_radius_km"
    assert const.CONF_PROVIDER_AUTO_CANCEL == "provider_auto_cancel"
    assert const.CONF_PROVIDER_MIN_SEVERITY == "provider_min_severity"


def test_provider_defaults():
    assert const.DEFAULT_PROVIDER_POLL_INTERVAL == 60
    assert const.PROVIDER_POLL_INTERVAL_MIN == 30
    assert const.PROVIDER_POLL_INTERVAL_MAX == 300
    assert const.DEFAULT_PROVIDER_AUTO_CANCEL is True
    assert const.DEFAULT_PROVIDER_MIN_SEVERITY == "severe"


def test_severity_levels_ordered():
    assert const.SEVERITY_LEVELS == ["minor", "moderate", "severe", "extreme"]
    assert const.SEVERITY_RANK["severe"] > const.SEVERITY_RANK["moderate"]
