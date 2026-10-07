#!/usr/bin/env python3
"""Rank scored quotes (score.py output on stdin) by total delivered cost.

Defaults for --gallons / --min-score / --max-age-days / allow+blocklists come from config.
  --benchmark 3.65     state-average $/gal to compare against (e.g. EIA weekly NH price)
  --format md|json
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
from lib.rank import rank
from lib.render import render_markdown


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gallons", type=float)
    ap.add_argument("--min-score", type=float)
    ap.add_argument("--max-age-days", type=int)
    ap.add_argument("--benchmark", type=float)
    ap.add_argument("--format", choices=("md", "json"), default="md")
    args = ap.parse_args()

    cfg = merge_defaults(load_config() or {})
    gallons = args.gallons or cfg["gallons"]
    data = json.load(sys.stdin)
    result = rank(
        data["quotes"], gallons=gallons,
        min_score=cfg["min_score"] if args.min_score is None else args.min_score,
        max_age_days=cfg["max_age_days"] if args.max_age_days is None else args.max_age_days,
        allowlist=cfg.get("allowlist") or [], blocklist=cfg.get("blocklist") or [],
    )
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_markdown(result, gallons, data.get("zip") or "", args.benchmark), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
