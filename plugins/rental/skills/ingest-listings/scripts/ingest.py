#!/usr/bin/env python3
"""Parse a Redfin CSV export into normalized 2-4 unit Property JSON on stdout."""
import argparse
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.listings import parse_redfin_csv, SchemaError


def main() -> int:
    ap = argparse.ArgumentParser(description="Redfin CSV -> normalized Property JSON")
    ap.add_argument("csv_path", help="Path to a Redfin 'Download All' CSV export")
    args = ap.parse_args()
    with open(args.csv_path, encoding="utf-8") as f:
        text = f.read()
    try:
        props, stats = parse_redfin_csv(text)
    except SchemaError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps([p.to_dict() for p in props]))
    print(f"ingested {stats['kept']}/{stats['total']} rows as 2-4 unit "
          f"({stats['dropped_type']} dropped by property type)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
