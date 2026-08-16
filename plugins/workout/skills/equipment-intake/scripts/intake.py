#!/usr/bin/env python3
"""CLI: record which equipment the user owns into the local SQLite store.

Usage:
    python intake.py --list                          # show all known equipment ids
    python intake.py --set dumbbell,pull_up_bar,sled  # replace the saved profile
    python intake.py --show                           # print the current profile
    python intake.py --reseed                         # refresh reference tables from references/
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import advisor  # noqa: E402
import seed  # noqa: E402
import store  # noqa: E402
import validation  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list all known equipment ids and names")
    parser.add_argument("--set", metavar="IDS", help="comma-separated equipment_ids to save as the profile")
    parser.add_argument("--show", action="store_true", help="print the currently saved profile")
    parser.add_argument("--reseed", action="store_true",
                        help="re-seed the exercise/equipment/source tables from references/, "
                             "overwriting whatever is already there (use after a plugin update)")
    parser.add_argument("--db", metavar="PATH", help="override the SQLite db path (mainly for tests)")
    args = parser.parse_args(argv)

    conn = store.connect(args.db)

    if args.reseed:
        print(json.dumps({"reseeded": seed.seed_all(conn)}))
        return 0

    if args.list:
        catalog = advisor.load_equipment_catalog()
        for item in catalog:
            print(f"{item['equipment_id']:20s} {item['name']}")
        return 0

    if args.set is not None:
        try:
            ids = validation.validate_equipment(validation.split_tokens(args.set))
        except validation.TokenError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        store.save_equipment_profile(conn, ids, dt.date.today().isoformat())
        print(json.dumps({"saved": ids}))
        return 0

    if args.show:
        print(json.dumps({"equipment_profile": store.get_equipment_profile(conn)}))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
