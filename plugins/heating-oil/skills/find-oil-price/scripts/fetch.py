#!/usr/bin/env python3
"""Fetch heating oil dealer prices and print merged, normalized quotes JSON.

Sources (any combination; each fails independently with a warning on stderr):
  --zone NH:10            newenglandoil.com state zone (repeatable)
  --url URL               any page with a dealer price table (repeatable)
  --manual FILE|-         quotes JSON you or Claude gathered (WebSearch, phone calls)
With no source flags, uses sources.newenglandoil_zones / sources.urls from config.
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

from lib.config import load_config, merge_defaults
from lib.dedupe import merge_quotes
from lib.http import fetch_text
from lib.sources.html_table import parse_tables
from lib.sources.manual import parse_manual
from lib.sources.newenglandoil import fetch_zone, state_for_zip, state_index_url


def _zone(s: str) -> dict:
    st, _, z = s.partition(":")
    if not z.isdigit():
        raise argparse.ArgumentTypeError("zone must look like NH:10")
    return {"state": st.upper(), "zone": int(z)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", help="your ZIP (default: config)")
    ap.add_argument("--zone", type=_zone, action="append", default=[])
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--manual", help="quotes JSON file, or - for stdin")
    args = ap.parse_args()

    cfg = merge_defaults(load_config() or {})
    zip_code = args.zip or cfg.get("zip")
    zones, urls = args.zone, args.url
    if not (zones or urls or args.manual):
        zones = cfg["sources"].get("newenglandoil_zones") or []
        urls = cfg["sources"].get("urls") or []
    if not (zones or urls or args.manual):
        st = state_for_zip(zip_code) if zip_code else None
        hint = (f"pick your zone at {state_index_url(st)} and pass --zone {st}:N"
                if st else "this ZIP is outside newenglandoil.com coverage; pass --url or --manual")
        print(f"error: no sources configured — {hint}", file=sys.stderr)
        return 2

    quotes = []
    for z in zones:
        try:
            got = fetch_zone(z["state"], z["zone"])
            print(f"newenglandoil {z['state']}-zone{z['zone']}: {len(got)} dealers", file=sys.stderr)
            quotes += got
        except Exception as e:  # one bad source must not sink the rest
            print(f"warning: newenglandoil {z}: {e}", file=sys.stderr)
    for u in urls:
        try:
            got = parse_tables(fetch_text(u), source=u.split("/")[2], base_url=u)
            print(f"{u}: {len(got)} dealers", file=sys.stderr)
            if not got:
                print(f"warning: no dealer price table recognized at {u}", file=sys.stderr)
            quotes += got
        except Exception as e:
            print(f"warning: {u}: {e}", file=sys.stderr)
    if args.manual:
        f = sys.stdin if args.manual == "-" else open(args.manual, encoding="utf-8")
        with f:
            quotes += parse_manual(json.load(f))

    merged = merge_quotes(quotes)
    print(json.dumps({"zip": zip_code, "quotes": [q.to_dict() for q in merged]}, indent=2))
    return 0 if merged else 1


if __name__ == "__main__":
    sys.exit(main())
