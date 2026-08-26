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


# Referenced, not copied: below one slot's worth of minutes nothing can be
# built, and a duplicated literal here would silently drift from the generator.
MIN_MINUTES = generator.MINUTES_PER_SLOT
MAX_DAYS = 7


class BuildError(Exception):
    """A user-facing, actionable failure -- printed as a message, not a traceback."""


def _choose_template(all_templates, exercises, level, days, minutes, equipment, constraints):
    """Walk every qualifying template best-fit-first and return the first one
    that is actually buildable for this user, as (template, buildability).

    Returns (None, reason) when none is usable -- `reason` describes why the
    *best* candidate failed, which is the one the user would have expected to
    get. Trying only the head of the list is how a user whose top template
    conflicts with a constraint ends up on the generator's identical-every-day
    fallback when a runner-up template would have fit them fine.
    """
    first_reason = None
    for candidate in templates_mod.rank_candidates(all_templates, level, equipment, days):
        if not templates_mod.fits_time_budget(candidate, minutes):
            reason = (
                f"its sessions run ~{candidate['session_minutes']} min, longer than the "
                f"~{minutes} min you have"
            )
        else:
            report = generator.template_buildability(candidate, exercises, equipment, constraints)
            if report["buildable"]:
                return candidate, report
            reason = report["reason"]
        first_reason = first_reason or reason
    return None, first_reason or (
        "no curated template matches this level/day count with the equipment you own"
    )


def build(level: str, days: int, minutes: int, equipment: list, constraints: list, block_weeks, conn,
          focus=None):
    """Template ranking -> buildability check -> generator fallback -> validate -> save.

    `focus`, when given, skips template matching entirely (v1 templates are
    all full-body) and builds a single-focus split routine instead, cycling
    across `days` if there are fewer focuses than days.

    Returns (program, program_id, notes).
    """
    exercises = exercises_mod.load_exercises()

    if focus:
        program = generator.generate_focus_program(
            exercises, focus_list=focus, equipment_profile=equipment, constraints=constraints,
            level=level, days_per_week=days, session_minutes=minutes, block_weeks=block_weeks or 8,
            created=dt.date.today().isoformat(),
        )
        notes = [f"Built a {', '.join(focus)} split routine."]
        if not any(s.exercises for w in program.weeks for s in w.sessions):
            raise BuildError(
                "No eligible exercises found for your equipment/constraints in this split. "
                "Loosen a constraint, or run equipment-advisor to see what to buy."
            )
        errors = model.validate_program(program)
        if errors:
            raise ValueError("generated program failed validation: " + "; ".join(errors))
        program_id = store.save_program(conn, program)
        return program, program_id, notes

    all_templates = templates_mod.load_all_templates()
    # `outcome` is the buildability report when a template was chosen, and the
    # reason the best candidate was rejected when none was.
    match, outcome = _choose_template(
        all_templates, exercises, level, days, minutes, equipment, constraints)

    notes = []
    if match is not None:
        if block_weeks and block_weeks != match["block_weeks"]:
            match = dict(match, block_weeks=block_weeks)
        program = generator.build_program_from_template(
            match, exercises, equipment_profile=equipment, constraints=constraints,
            created=dt.date.today().isoformat(),
        )
        notes.append(f"Used curated template: {match['template_id']}")
        if program.meta.session_minutes != minutes:
            notes.append(
                f"This template's sessions run ~{program.meta.session_minutes} min, not the "
                f"~{minutes} min you asked for -- the printed length is the program's real one."
            )
        for pattern in outcome["skipped_patterns"]:
            notes.append(
                f"Dropped the {pattern} slot: nothing you own trains that pattern within your "
                f"constraints. Run equipment-advisor to see what would unlock it."
            )
    else:
        notes.append(f"No template fit ({outcome}); generated a program from the eligible exercise pool.")
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
    parser.add_argument("--focus", default="",
                         help="comma-separated split focuses (core,legs,arms); cycles across --days. "
                              "When set, skips curated templates entirely.")
    parser.add_argument("--block-weeks", type=int, default=None)
    parser.add_argument("--format", choices=["markdown", "csv", "json"], default="markdown")
    parser.add_argument("--out", required=True, help="output file path")
    parser.add_argument("--db", metavar="PATH", help="override the SQLite db path (mainly for tests)")
    args = parser.parse_args(argv)

    # Bounds first: --minutes 0 or --days 0 otherwise reaches validate_program
    # and comes back out as an uncaught ValueError traceback, which is exactly
    # what BuildError exists to prevent.
    if args.minutes < MIN_MINUTES:
        print(f"error: --minutes must be at least {MIN_MINUTES}, got {args.minutes}", file=sys.stderr)
        return 2
    if not 1 <= args.days <= MAX_DAYS:
        print(f"error: --days must be between 1 and {MAX_DAYS}, got {args.days}", file=sys.stderr)
        return 2
    if args.block_weeks is not None and args.block_weeks < 1:
        print(f"error: --block-weeks must be at least 1, got {args.block_weeks}", file=sys.stderr)
        return 2

    try:
        equipment = validation.validate_equipment(validation.split_tokens(args.equipment))
        constraints = validation.validate_constraints(validation.split_tokens(args.constraints))
        focus = validation.validate_focus(validation.split_tokens(args.focus))
    except validation.TokenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    conn = store.connect(args.db)
    try:
        program, program_id, notes = build(args.level, args.days, args.minutes, equipment,
                                            constraints, args.block_weeks, conn, focus=focus)
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
