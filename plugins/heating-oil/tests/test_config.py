import json

import pytest

from lib import config


@pytest.fixture
def cfg_env(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    monkeypatch.setenv("HEATING_OIL_CONFIG", str(p))
    return p


def test_first_run_has_no_config(cfg_env):
    assert config.load_config() is None
    with pytest.raises(FileNotFoundError):
        config.load_merged()


def test_write_and_merge_defaults(cfg_env):
    config.write_config({"zip": "03801", "sources": {"newenglandoil_zones": [{"state": "NH", "zone": 10}]}})
    m = config.load_merged()
    assert m["zip"] == "03801" and m["gallons"] == 150 and m["min_score"] == 70
    assert m["sources"]["urls"] == []
    assert config.cache_path().parent == cfg_env.parent


def test_validation_errors(cfg_env):
    with pytest.raises(config.ConfigError, match="zip"):
        config.write_config({"zip": "3801"})
    errs = config.validate(config.merge_defaults(
        {"zip": "03801", "gallons": 0, "sources": {"newenglandoil_zones": [{"state": "NH"}]}}))
    assert any("gallons" in e for e in errs) and any("zone" in e for e in errs)


def test_weights_sum_to_one():
    w = config.load_reference("reputation-weights.json")["weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-9
