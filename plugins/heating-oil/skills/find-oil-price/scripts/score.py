#!/usr/bin/env python3
"""Attach a reputation score to each quote. Reads fetch.py output on stdin.

  --reputation FILE    {dealer_key: signals} from your WebSearch research (see SKILL.md)
  --save-cache         store those signals in the local dealer cache for next time
  --todo N             instead of scoring, list the N cheapest dealers that still
                       need research (not in --reputation or a fresh cache entry)
"""
import argparse
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from lib.cache import fresh_entries, load_cache, save_cache
from lib.config import load_config, merge_defaults
from lib.models import Quote
from lib.reputation import score_dealer


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reputation")
    ap.add_argument("--save-cache", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--todo", type=int, metavar="N")
    args = ap.parse_args()

    data = json.load(sys.stdin)
    cfg = merge_defaults(load_config() or {})
    cache = {} if args.no_cache else load_cache()
    signals = fresh_entries(cache, cfg["cache_ttl_days"])
    provided = {}
    if args.reputation:
        with open(args.reputation, encoding="utf-8") as f:
            provided = json.load(f)
        signals.update(provided)

    quotes = [Quote.from_dict(d) for d in data["quotes"]]
    if args.todo is not None:
        need = [q for q in quotes if q.to_dict()["key"] not in signals]
        need.sort(key=lambda q: min(q.tiers.values()))
        print(json.dumps([{"key": q.to_dict()["key"], "dealer": q.dealer, "town": q.town,
                           "phone": q.phone, "url": q.url, "lowest_price": min(q.tiers.values())}
                          for q in need[:args.todo]], indent=2))
        return 0

    out = []
    for q in quotes:
        d = q.to_dict()
        d["reputation"] = score_dealer(q, signals.get(d["key"]))
        out.append(d)
    if args.save_cache and provided:
        save_cache(cache, provided)
    print(json.dumps({**data, "quotes": out}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
