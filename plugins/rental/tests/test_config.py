import json
import pytest
from lib import config as cfg


def test_config_path_honors_env(monkeypatch, tmp_path):
    target = tmp_path / "myconfig.json"
    monkeypatch.setenv("RENTAL_CONFIG", str(target))
    assert cfg.config_path() == target


def test_config_path_uses_appdata_on_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("RENTAL_CONFIG", raising=False)
    monkeypatch.setattr(cfg.os, "name", "nt")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = cfg.config_path()
    assert p == tmp_path / "personal-os" / "rental" / "config.json"


def test_load_config_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("RENTAL_CONFIG", str(tmp_path / "nope.json"))
    assert cfg.load_config() is None


def test_merge_defaults_overlays_user_values():
    merged = cfg.merge_defaults({"financing": {"down_payment_pct": 0.20}})
    assert merged["financing"]["down_payment_pct"] == 0.20      # overridden
    assert merged["financing"]["loan_term_years"] == 30          # from defaults
    assert merged["expenses"]["vacancy_pct"] == 0.05             # from defaults


def test_validate_flags_missing_market_and_bad_ranges():
    errors = cfg.validate(cfg.merge_defaults({"financing": {"down_payment_pct": 2.0}}))
    assert any("market" in e for e in errors)          # market required, absent
    assert any("down_payment_pct" in e for e in errors)  # must be 0..1


def test_validate_passes_on_complete_config():
    good = cfg.merge_defaults({
        "market": {"label": "Springfield, IL", "zips": ["62701"]},
        "rentcast_api_key": "test-key",
    })
    assert cfg.validate(good) == []
