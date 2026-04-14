"""Constants regression test for FR-Alert provider config keys."""
from custom_components.shelter_finder import const


def test_provider_conf_keys_present():
    assert const.CONF_PROVIDER_GEORISQUES == "provider_georisques"
    assert const.CONF_PROVIDER_METEO_FRANCE == "provider_meteo_france"
    assert const.CONF_POLLING_INTERVAL == const.CONF_PROVIDER_POLL_INTERVAL
    assert const.CONF_ALERT_RADIUS == const.CONF_PROVIDER_ALERT_RADIUS_KM
    assert const.CONF_AUTO_CANCEL == const.CONF_PROVIDER_AUTO_CANCEL
    assert const.CONF_MIN_SEVERITY == const.CONF_PROVIDER_MIN_SEVERITY


def test_provider_defaults():
    assert const.DEFAULT_POLLING_INTERVAL == 60
    assert const.MIN_POLLING_INTERVAL == 30
    assert const.MAX_POLLING_INTERVAL == 300
    assert const.DEFAULT_AUTO_CANCEL is True
    assert const.DEFAULT_MIN_SEVERITY == "severe"


def test_severity_levels_ordered():
    assert const.SEVERITY_LEVELS == ["minor", "moderate", "severe", "extreme"]
    assert const.SEVERITY_RANK["severe"] > const.SEVERITY_RANK["moderate"]
