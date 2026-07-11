"""Config location, loading, default-merging, and validation.

Config lives OUTSIDE the repo (it holds an API key + personal assumptions):
  Windows:      %APPDATA%\\personal-os\\rental\\config.json
  macOS/Linux:  ~/.config/personal-os/rental/config.json
Override with the RENTAL_CONFIG env var. Absent file == first run.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path


class ConfigError(Exception):
    pass


def config_path() -> Path:
    override = os.environ.get("RENTAL_CONFIG")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "personal-os" / "rental" / "config.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "personal-os" / "rental" / "config.json"


def defaults_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "expense-defaults.json"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict | None:
    p = config_path()
    if not p.is_file():
        return None
    return _load_json(p)


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def merge_defaults(user: dict) -> dict:
    defaults = {k: v for k, v in _load_json(defaults_path()).items()
                if not k.startswith("_")}
    return _deep_merge(defaults, user or {})


def _in_unit_interval(x) -> bool:
    return isinstance(x, (int, float)) and 0 <= x <= 1


def validate(cfg: dict) -> list[str]:
    errors: list[str] = []
    market = cfg.get("market") or {}
    if not market.get("label"):
        errors.append("market.label is required (e.g. 'Springfield, IL')")
    if not market.get("zips"):
        errors.append("market.zips must list at least one ZIP code")
    if not cfg.get("rentcast_api_key"):
        errors.append("rentcast_api_key is required for the enrichment step")
    fin = cfg.get("financing", {})
    for key in ("down_payment_pct", "closing_cost_pct"):
        if not _in_unit_interval(fin.get(key)):
            errors.append(f"financing.{key} must be a fraction between 0 and 1")
    if not isinstance(fin.get("loan_term_years"), (int, float)) or fin.get("loan_term_years") <= 0:
        errors.append("financing.loan_term_years must be a positive number")
    exp = cfg.get("expenses", {})
    for key in ("vacancy_pct", "maintenance_pct", "capex_pct", "management_pct",
                "property_tax_pct_fallback"):
        if not _in_unit_interval(exp.get(key)):
            errors.append(f"expenses.{key} must be a fraction between 0 and 1")
    return errors


def load_merged() -> dict:
    user = load_config()
    if user is None:
        raise FileNotFoundError(str(config_path()))
    merged = merge_defaults(user)
    errors = validate(merged)
    if errors:
        raise ConfigError("; ".join(errors))
    return merged
