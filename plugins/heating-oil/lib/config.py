"""Config location, loading, default-merging, and validation.

Config lives OUTSIDE the repo (it holds your ZIP + dealer research cache):
  Windows:      %APPDATA%\\personal-os\\heating-oil\\config.json
  macOS/Linux:  ~/.config/personal-os/heating-oil/config.json
Override with the HEATING_OIL_CONFIG env var. Absent file == first run.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path


class ConfigError(Exception):
    pass


def config_path() -> Path:
    override = os.environ.get("HEATING_OIL_CONFIG")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "personal-os" / "heating-oil" / "config.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "personal-os" / "heating-oil" / "config.json"


def cache_path() -> Path:
    return config_path().parent / "dealer-cache.json"


def references_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "references"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"{path} is not valid JSON: {e}") from e


def load_reference(name: str) -> dict:
    return {k: v for k, v in _load_json(references_dir() / name).items()
            if not k.startswith("_")}


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
    return _deep_merge(load_reference("defaults.json"), user or {})


def validate(cfg: dict) -> list[str]:
    errors: list[str] = []
    if not re.fullmatch(r"\d{5}", str(cfg.get("zip") or "")):
        errors.append("zip must be a 5-digit US ZIP code")
    g = cfg.get("gallons")
    if not isinstance(g, (int, float)) or g <= 0:
        errors.append("gallons must be a positive number")
    s = cfg.get("min_score")
    if not isinstance(s, (int, float)) or not 0 <= s <= 100:
        errors.append("min_score must be between 0 and 100")
    a = cfg.get("max_age_days")
    if not isinstance(a, (int, float)) or a < 0:
        errors.append("max_age_days must be a non-negative number")
    for z in (cfg.get("sources") or {}).get("newenglandoil_zones") or []:
        if not isinstance(z, dict) or not z.get("state") or not isinstance(z.get("zone"), int):
            errors.append(f"sources.newenglandoil_zones entry {z!r} needs 'state' and integer 'zone'")
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


def write_config(cfg: dict) -> Path:
    errors = validate(merge_defaults(cfg))
    if errors:
        raise ConfigError("; ".join(errors))
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return p
