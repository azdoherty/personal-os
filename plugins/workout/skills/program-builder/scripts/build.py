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
import advisor  # noqa: E402
import exercises as exercises_mod  # noqa: E402
import generator  # noqa: E402
import model  # noqa: E402
import render  # noqa: E402
import store  # noqa: E402
import templates as templates_mod  # noqa: E402
import validation  # noqa: E402


class BuildError(Exception):
    """A user-facing, actionable failure -- printed as a message, not a traceback."""


def build(level: str, days: int, minutes: int, equipment: list, constraints: list, block_weeks, conn):
    """Template match -> buildability check -> generator fallback -> validate -> save.

    Returns (program, program_id, notes).
    """
    exercises = exercises_mod.load_exercises()
    all_templates = templates_mod.load_all_templates()
    match = templates_mod.match_template(all_templates, level, equipment, days)

    notes = []
    buildability = None
    if match is not None:
        buildability = generator.template_buildability(match, exercises, equipment, constraints)

    if buildability is not None and buildability["buildable"]:
        if block_weeks and block_weeks != match["block_weeks"]:
            match = dict(match, block_weeks=block_weeks)
        program = generator.build_program_from_template(
            match, exercises, equipment_profile=equipment, constraints=constraints,
            created=dt.date.today().isoformat(), session_minutes=minutes,
        )
        notes.append(f"Used curated template: {match['template_id']}")
        for pattern in buildability["skipped_patterns"]:
            notes.append(
                f"Dropped the {pattern} slot: nothing you own trains that pattern within your "
                f"constraints. Run equipment-advisor to see what would unlock it."
            )
    else:
        if match is None:
            reason = "no curated template matches this level/day count with the equipment you own"
        else:
            reason = buildability["reason"]
        notes.append(f"No template fit ({reason}); generated a program from the eligible exercise pool.")
        program = generator.generate_program(
            exercises, equipment_profile=equipment, constraints=constraints, level=level,
            days_per_week=days, session_minutes=minutes, block_weeks=block_weeks or 8,
            created=dt.date.today().isoformat(),
        )
        missing = advisor.thin_or_missing_patterns(exercises, equipment, constraints, threshold=1)
        if missing:
            notes.append(
                "No eligible exercise at all for: " + ", ".join(missing) +
                " -- your program has no coverage there."
            )

    if not any(s.exercises for w in program.weeks for s in w.sessions):
        uncovered = advisor.thin_or_missing_patterns(exercises, equipment, constraints, threshold=1)
        raise BuildError(
            "No eligible exercises found for your equipment/constraints "
            f"(uncovered patterns: {', '.join(uncovered) or 'all'}). "
            "Loosen a constraint, or run equipment-advisor to see what to buy."
        )

    errors = model.validate_program(program)
    if errors:
        raise ValueError("generated program failed validation: " + "; ".join(errors))

    program_id = store.save_program(conn, program)
    return program, program_id, notes


def main(argv=None) -> int:
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
    args = parser.parse_args(argv)

    try:
        equipment = validation.validate_equipment(validation.split_tokens(args.equipment))
        constraints = validation.validate_constraints(validation.split_tokens(args.constraints))
    except validation.TokenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    conn = store.connect(args.db)
    try:
        program, program_id, notes = build(args.level, args.days, args.minutes, equipment,
                                            constraints, args.block_weeks, conn)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    renderer = {"markdown": render.render_markdown, "csv": render.render_csv, "json": render.render_json}
    text = renderer[args.format](program)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    for note in notes:
        print(note)
    print(f"Saved as {program_id}")
    print(f"Wrote {args.format} program to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
