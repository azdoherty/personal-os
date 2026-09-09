#!/usr/bin/env python3
"""Enrich a pruned Property[] with RentCast rent estimates + comps. Metered: one
RentCast call per uncached property. Reads/writes the pruned list as JSON."""
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.config import load_merged, ConfigError
from lib.models import Property
from lib.rentcast import enrich_property, QuotaError, RentCastError

CACHE_PATH = os.path.join(os.getcwd(), "rentcast.cache.json")


def _load_cache() -> dict:
    if os.path.isfile(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def main() -> int:
    try:
        cfg = load_merged()
    except FileNotFoundError:
        print("error: no config found — run /setup first", file=sys.stderr)
        return 3
    except ConfigError as e:
        print(f"error: invalid config: {e}", file=sys.stderr)
        return 3
    api_key = cfg["rentcast_api_key"]
    raw = json.load(sys.stdin)
    raw = [d["property"] if isinstance(d, dict) and "property" in d and "scenarios" in d else d
           for d in raw]
    props = [Property.from_dict(d) for d in raw]
    cache = _load_cache()
    enriched, spent = [], 0
    exit_code = 0
    for prop in props:
        before = len(cache)
        try:
            enrich_property(prop, api_key, cache)
            spent += (len(cache) - before)
        except QuotaError as e:
            prop.notes.append(f"not enriched: {e}")
            print(f"warning: RentCast quota/limit reached after {spent} calls; "
                  f"stopping enrichment. Remaining properties left un-enriched.",
                  file=sys.stderr)
            enriched.append(prop)
            exit_code = 4
            break
        except RentCastError as e:
            prop.notes.append(f"enrichment failed: {e}")
        enriched.append(prop)
    # append any properties after a quota break, un-enriched
    seen = {id(p) for p in enriched}
    for prop in props:
        if id(prop) not in seen:
            prop.notes.append(
                "not enriched: RentCast quota reached before this property was attempted"
            )
            enriched.append(prop)
    _save_cache(cache)
    print(json.dumps([p.to_dict() for p in enriched]))
    print(f"enriched with {spent} RentCast call(s); cache at {CACHE_PATH}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
