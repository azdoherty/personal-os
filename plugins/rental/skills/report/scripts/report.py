#!/usr/bin/env python3
"""Read enriched Property[] JSON on stdin, re-underwrite with real rents + live rate,
and write a ranked markdown report + CSV."""
import argparse
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.config import load_merged, ConfigError
from lib.models import Property, DealResult
from lib.rates import effective_rate
from lib.underwrite import build_scenarios, compute_returns
from lib.report import render_markdown, render_csv


def main() -> int:
    ap = argparse.ArgumentParser(description="Render rental report from enriched JSON")
    ap.add_argument("--out-dir", default=os.getcwd())
    ap.add_argument("--strict-cashflow", action="store_true")
    args = ap.parse_args()
    try:
        cfg = load_merged()
    except FileNotFoundError:
        print("error: no config found — run /setup first", file=sys.stderr)
        return 3
    except ConfigError as e:
        print(f"error: invalid config: {e}", file=sys.stderr)
        return 3

    props = [Property.from_dict(d) for d in json.load(sys.stdin)]
    rate, note = effective_rate(cfg)
    results = []
    for p in props:
        if not (p.gross_monthly_rent and p.list_price):
            continue
        scenarios, max_price = build_scenarios(p, cfg, rate, args.strict_cashflow)
        asking = compute_returns(p, cfg, p.list_price, rate, args.strict_cashflow)
        results.append(DealResult(p, scenarios, max_price, rate,
                                  rank_metric=asking["cash_on_cash"], notes=list(p.notes)))
    results.sort(key=lambda r: r.rank_metric, reverse=True)

    md = render_markdown(results, cfg, note)
    csv_text = render_csv(results)
    md_path = os.path.join(args.out_dir, "rental-report.md")
    csv_path = os.path.join(args.out_dir, "rental-report.csv")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_text)
    print(md)
    print(f"wrote {md_path} and {csv_path} ({len(results)} properties)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
