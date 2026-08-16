"""Renderers: pure functions that turn a Program into printable output. No
business logic here -- the program is already fully computed.
"""
from __future__ import annotations

import csv
import io
import json

from model import Program


def _fmt_load(load) -> str:
    if load.type == "bodyweight":
        return "Bodyweight"
    if load.value is None:
        return "____ lb (start light, log it)"
    return f"{load.value:g} lb"


def render_markdown(program: Program) -> str:
    meta = program.meta
    out = io.StringIO()
    out.write(f"# {program.progression.block_weeks}-Week Home Strength Program — {meta.level.title()}\n\n")
    out.write(
        f"**Goal:** {meta.goal.replace('_', ' ').title()}  \n"
        f"**Days/week:** {meta.days_per_week}  \n"
        f"**Session length:** ~{meta.session_minutes} min  \n"
        f"**Equipment:** {', '.join(meta.equipment_profile) or 'bodyweight only'}  \n"
        f"**Constraints honored:** {', '.join(meta.constraints) or 'none'}  \n"
        f"**Source:** {meta.source}  \n"
        f"**Progression model:** {program.progression.model}\n\n"
        "> This is a general fitness program, not medical advice — consult a professional "
        "for any injury or medical condition.\n\n"
    )
    for week in program.weeks:
        out.write(f"## Week {week.number}\n\n")
        for session in week.sessions:
            out.write(f"### Day {session.day} — {session.label}\n\n")
            out.write("| Exercise | Sets | Reps | Load | Tempo | Rest | Done | Actual reps | RPE | Notes |\n")
            out.write("|---|---|---|---|---|---|---|---|---|---|\n")
            for ex in session.exercises:
                out.write(
                    f"| {ex.name} | {ex.sets} | {ex.reps} | {_fmt_load(ex.load)} | {ex.tempo} | "
                    f"{ex.rest} | [ ] | ____ | ____ | {ex.notes} |\n"
                )
            out.write("\n")
    return out.getvalue()


def render_csv(program: Program) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "week", "day", "session_label", "exercise", "sets", "target_reps", "load_type",
        "load_value", "tempo", "rest", "notes", "actual_reps", "actual_load", "rpe", "pain",
    ])
    for week in program.weeks:
        for session in week.sessions:
            for ex in session.exercises:
                writer.writerow([
                    week.number, session.day, session.label, ex.name, ex.sets, ex.reps,
                    ex.load.type, "" if ex.load.value is None else ex.load.value, ex.tempo,
                    ex.rest, ex.notes, "", "", "", "",
                ])
    return out.getvalue()


def render_json(program: Program) -> str:
    return json.dumps(program.to_dict(), indent=2, ensure_ascii=False)
