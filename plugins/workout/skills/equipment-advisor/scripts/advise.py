#!/usr/bin/env python3
"""CLI: rank equipment gaps by how much new training value they'd unlock.

Usage:
    python advise.py --owned dumbbell,sled --constraints arm-load,grip
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import advisor  # noqa: E402
import exercises as exercises_mod  # noqa: E402
import validation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owned", default="", help="comma-separated equipment_ids already owned")
    parser.add_argument("--constraints", default="", help="comma-separated constraint flags to avoid")
    parser.add_argument("--top", type=int, default=5, help="how many ranked recommendations to print")
    args = parser.parse_args()

    try:
        owned = validation.validate_equipment(validation.split_tokens(args.owned))
        constraints = validation.validate_constraints(validation.split_tokens(args.constraints))
    except validation.TokenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    exercises = exercises_mod.load_exercises()
    catalog = advisor.load_equipment_catalog()

    thin = advisor.thin_or_missing_patterns(exercises, owned, constraints)
    ranked = advisor.rank_equipment_gaps(exercises, catalog, owned, constraints)[: args.top]
    bundles = advisor.find_equipment_bundles(exercises, catalog, owned, constraints)

    print(json.dumps({
        "thin_or_missing_patterns": thin,
        "recommendations": ranked,
        "bundles": bundles,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
