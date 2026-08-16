#!/usr/bin/env python3
"""CLI: build a progressive home-strength program and write printable output.

Usage:
    python build.py --level beginner --days 3 --minutes 30 \
        --equipment dumbbell --constraints arm-load,grip \
        --block-weeks 8 --format markdown --out program.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import exercises as exercises_mod  # noqa: E402
import generator  # noqa: E402
import model  # noqa: E402
import render  # noqa: E402
import store  # noqa: E402
import templates as templates_mod  # noqa: E402


def build(level: str, days: int, minutes: int, equipment: list, constraints: list, block_weeks, conn):
    exercises = exercises_mod.load_exercises()
    all_templates = templates_mod.load_all_templates()
    match = templates_mod.match_template(all_templates, level, equipment, days)

    notes = []
    if match is not None and generator.template_is_constraint_compatible(match, exercises, constraints):
        if block_weeks and block_weeks != match["block_weeks"]:
            match = dict(match, block_weeks=block_weeks)
        program = generator.build_program_from_template(
            match, exercises, equipment_profile=equipment, constraints=constraints,
            created=dt.date.today().isoformat(),
        )
        notes.append(f"Used curated template: {match['template_id']}")
    else:
        reason = "no curated template matches this equipment/day count" if match is None else \
            "the closest template conflicts with your active constraints"
        notes.append(f"No template fit ({reason}); generated a program from the eligible exercise pool.")
        program = generator.generate_program(
            exercises, equipment_profile=equipment, constraints=constraints, level=level,
            days_per_week=days, session_minutes=minutes, block_weeks=block_weeks or 8,
            created=dt.date.today().isoformat(),
        )

    errors = model.validate_program(program)
    if errors:
        raise ValueError("generated program failed validation: " + "; ".join(errors))

    store.save_program(conn, program)
    return program, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", required=True, choices=list(model.LEVELS))
    parser.add_argument("--days", required=True, type=int)
    parser.add_argument("--minutes", required=True, type=int)
    parser.add_argument("--equipment", default="", help="comma-separated equipment_ids owned")
    parser.add_argument("--constraints", default="", help="comma-separated constraint flags to avoid")
    parser.add_argument("--block-weeks", type=int, default=None)
    parser.add_argument("--format", choices=["markdown", "csv", "json"], default="markdown")
    parser.add_argument("--out", required=True, help="output file path")
    parser.add_argument("--db", metavar="PATH", help="override the SQLite db path (mainly for tests)")
    args = parser.parse_args()

    equipment = [e.strip() for e in args.equipment.split(",") if e.strip()]
    constraints = [c.strip() for c in args.constraints.split(",") if c.strip()]

    conn = store.connect(args.db)
    program, notes = build(args.level, args.days, args.minutes, equipment, constraints,
                            args.block_weeks, conn)

    renderer = {"markdown": render.render_markdown, "csv": render.render_csv, "json": render.render_json}
    text = renderer[args.format](program)
    Path(args.out).write_text(text, encoding="utf-8")

    for note in notes:
        print(note)
    print(f"Wrote {args.format} program to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
