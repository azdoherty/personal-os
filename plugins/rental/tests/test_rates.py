import pytest
from lib import rates


SAMPLE_FRED = (
    "observation_date,MORTGAGE30US\n"
    "2026-06-18,6.81\n"
    "2026-06-25,6.87\n"
    "2026-07-02,.\n"          # FRED uses '.' for missing; must be skipped
)


def test_parse_fred_takes_last_numeric_as_fraction():
    assert rates.parse_fred_csv(SAMPLE_FRED) == pytest.approx(0.0687)


def test_parse_fred_raises_on_no_numbers():
    with pytest.raises(ValueError):
        rates.parse_fred_csv("observation_date,MORTGAGE30US\n2026-07-02,.\n")


def test_effective_rate_uses_pin_when_set():
    cfg = {"financing": {"rate_pin_pct": 0.065, "rate_spread_pct": 0.0075}}
    rate, note = rates.effective_rate(cfg)
    assert rate == 0.065
    assert "pin" in note.lower()


def test_effective_rate_adds_spread_to_benchmark(monkeypatch):
    monkeypatch.setattr(rates, "fetch_benchmark", lambda timeout=15.0: 0.0687)
    cfg = {"financing": {"rate_pin_pct": None, "rate_spread_pct": 0.0075}}
    rate, note = rates.effective_rate(cfg)
    assert rate == pytest.approx(0.0762)
    assert "benchmark" in note.lower()


def test_effective_rate_falls_back_on_fetch_failure(monkeypatch):
    def boom(timeout=15.0):
        raise OSError("network down")
    monkeypatch.setattr(rates, "fetch_benchmark", boom)
    cfg = {"financing": {"rate_pin_pct": None, "rate_spread_pct": 0.0075}}
    rate, note = rates.effective_rate(cfg)
    assert rate == pytest.approx(0.07)
    assert "default" in note.lower()
