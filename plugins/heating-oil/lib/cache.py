"""Local cache of dealer reputation research (config dir, never the repo)."""
from __future__ import annotations

import json
from datetime import date

from lib.config import cache_path


def load_cache() -> dict:
    p = cache_path()
    if not p.is_file():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def fresh_entries(cache: dict, ttl_days: int, today: date | None = None) -> dict:
    today = today or date.today()
    out = {}
    for key, entry in cache.items():
        at = entry.get("researched_at")
        if at and (today - date.fromisoformat(at)).days <= ttl_days:
            out[key] = entry
    return out


def save_cache(cache: dict, updates: dict, today: date | None = None) -> None:
    stamp = (today or date.today()).isoformat()
    merged = dict(cache)
    for key, sig in updates.items():
        merged[key] = {**sig, "researched_at": sig.get("researched_at", stamp)}
    p = cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, sort_keys=True)
