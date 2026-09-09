"""Fetch the 30-year mortgage benchmark from FRED (no API key) and derive the
effective investment-property rate. Pure parsing is separated from the network
call so it can be unit-tested. All returned rates are fractions (0.0687 == 6.87%).
"""
from __future__ import annotations

import urllib.request

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
_DEFAULT_RATE = 0.07


def parse_fred_csv(text: str) -> float:
    latest: float | None = None
    for line in text.splitlines()[1:]:  # skip header
        parts = line.split(",")
        if len(parts) < 2:
            continue
        raw = parts[1].strip()
        try:
            latest = float(raw) / 100.0
        except ValueError:
            continue  # '.' or blank == missing observation
    if latest is None:
        raise ValueError("No numeric MORTGAGE30US observation found in FRED CSV")
    return latest


def fetch_benchmark(timeout: float = 15.0) -> float:
    req = urllib.request.Request(FRED_URL, headers={"User-Agent": "personal-os-rental/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", "replace")
    return parse_fred_csv(text)


def effective_rate(cfg: dict) -> tuple[float, str]:
    fin = cfg.get("financing", {})
    pin = fin.get("rate_pin_pct")
    spread = fin.get("rate_spread_pct", 0.0)
    if pin is not None:
        return pin, f"pinned rate {pin:.4f} from config"
    try:
        benchmark = fetch_benchmark()
        return benchmark + spread, (
            f"live FRED benchmark {benchmark:.4f} + spread {spread:.4f}"
        )
    except Exception as e:  # noqa: BLE001 - any network/parse failure falls back
        if pin is not None:
            return pin, f"pinned rate (benchmark fetch failed: {e})"
        return _DEFAULT_RATE, (
            f"labeled default {_DEFAULT_RATE:.4f} (benchmark fetch failed: {e})"
        )
