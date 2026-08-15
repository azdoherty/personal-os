#!/usr/bin/env python3
"""CLI: record which equipment the user owns into the local SQLite store.

Usage:
    python intake.py --list                          # show all known equipment ids
    python intake.py --set dumbbell,pull_up_bar,sled  # replace the saved profile
    python intake.py --show                           # print the current profile
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import advisor  # noqa: E402
import store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list all known equipment ids and names")
    parser.add_argument("--set", metavar="IDS", help="comma-separated equipment_ids to save as the profile")
    parser.add_argument("--show", action="store_true", help="print the currently saved profile")
    parser.add_argument("--db", metavar="PATH", help="override the SQLite db path (mainly for tests)")
    args = parser.parse_args()

    conn = store.connect(args.db)

    if args.list:
        catalog = advisor.load_equipment_catalog()
        for item in catalog:
            print(f"{item['equipment_id']:20s} {item['name']}")
        return 0

    if args.set is not None:
        ids = [i.strip() for i in args.set.split(",") if i.strip()]
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
