"""Program generation: builds a full Program either from a curated template
(templates.py) or, when no template fits the user's equipment/constraints,
by assembling one from the eligible exercise pool directly.
"""
from __future__ import annotations

from model import Program, ProgramMeta, Progression, Week, Session, ProgramExercise, LoadSpec
import exercises as exercises_mod
import progression as progression_mod

PATTERN_ORDER = ("squat", "hinge", "push", "pull", "core", "carry")
DEFAULT_WEEKS_PER_RUNG = 2
DEFAULT_SETS = 3
DEFAULT_REPS_LOW = 8
DEFAULT_REPS_HIGH = 12
DEFAULT_REP_STEP = 1
DEFAULT_LOAD_INCREMENT = 5.0


def template_is_constraint_compatible(template: dict, exercises: list, excluded_constraints) -> bool:
    """A template can only be used if every exercise slot has at least one
    option (a ladder rung, or the fixed exercise) that avoids every excluded
    constraint flag."""
    excluded = set(excluded_constraints)
    for session in template["sessions"]:
        for entry in session["exercises"]:
            if "ladder_group" in entry:
                ladder = exercises_mod.ladder_for_group(exercises, entry["ladder_group"])
                if not any(not (set(r.get("constraint_flags", [])) & excluded) for r in ladder):
                    return False
            else:
                ex = exercises_mod.find_by_id(exercises, entry["exercise_id"])
                if set(ex.get("constraint_flags", [])) & excluded:
                    return False
    return True


def _build_ladder_exercise(entry: dict, exercises: list, block_weeks: int) -> list:
    ladder = exercises_mod.ladder_for_group(exercises, entry["ladder_group"])
    weeks = progression_mod.generate_block(entry, block_weeks, "variation-ladder", ladder=ladder)
    movement_pattern = ladder[0]["movement_pattern"]
    rule = f"Progress to the next ladder rung every {entry['weeks_per_rung']} weeks."
    result = []
    for step in weeks:
        result.append(ProgramExercise(
            exercise_id=step["exercise_id"], name=step["name"], movement_pattern=movement_pattern,
            sets=entry["sets"], reps=step["reps"], load=LoadSpec(type="bodyweight", progression_rule=rule),
            tempo=entry["tempo"], rest=entry["rest"], notes=entry.get("notes", ""),
        ))
    return result


def _build_loaded_exercise(entry: dict, exercises: list, block_weeks: int, model_name: str) -> list:
    ex_meta = exercises_mod.find_by_id(exercises, entry["exercise_id"])
    weeks = progression_mod.generate_block(entry, block_weeks, model_name)
    if model_name == "double-progression":
        rule = (
            f"Add a rep each week; at {entry['reps_high']} reps for all sets, "
            f"add {entry['load_increment']}lb and reset to {entry['reps_low']} reps."
        )
    else:
        rule = (
            f"Add {entry.get('increment', DEFAULT_LOAD_INCREMENT)}lb every "
            f"{entry.get('increment_every_weeks', 1)} week(s)."
        )
    result = []
    for step in weeks:
        result.append(ProgramExercise(
            exercise_id=entry["exercise_id"], name=ex_meta["name"],
            movement_pattern=ex_meta["movement_pattern"], sets=entry["sets"], reps=step["reps"],
            load=LoadSpec(type="external", value=step["load_value"], progression_rule=rule),
            tempo=entry["tempo"], rest=entry["rest"], notes=entry.get("notes", ""),
        ))
    return result


def build_program_from_template(template: dict, exercises: list, equipment_profile: list,
                                 constraints: list, created: str) -> Program:
    block_weeks = template["block_weeks"]
    model_name = template["progression_model"]

    per_slot_weeks = []
    for session in template["sessions"]:
        slot_series = []
        for entry in session["exercises"]:
            if "ladder_group" in entry:
                slot_series.append(_build_ladder_exercise(entry, exercises, block_weeks))
            else:
                slot_series.append(_build_loaded_exercise(entry, exercises, block_weeks, model_name))
        per_slot_weeks.append((session["day"], session["label"], slot_series))

    weeks = []
    for week_number in range(1, block_weeks + 1):
        sessions = []
        for day, label, slot_series in per_slot_weeks:
            week_exercises = [series[week_number - 1] for series in slot_series]
            sessions.append(Session(day=day, label=label, exercises=week_exercises))
        weeks.append(Week(number=week_number, sessions=sessions))

    meta = ProgramMeta(
        level=template["level"], goal=template["goal"], days_per_week=template["days_per_week"],
        session_minutes=template["session_minutes"], equipment_profile=list(equipment_profile),
        constraints=list(constraints), created=created, source=template["template_id"],
    )
    return Program(meta=meta, progression=Progression(model=model_name, block_weeks=block_weeks), weeks=weeks)


def _pick_representative(pool: list) -> dict:
    """Deterministic pick: prefer a standalone, directly-loadable exercise
    (not part of a bodyweight ladder) when one is eligible, since that lets
    the fallback program actually use equipment the user owns. When only
    bodyweight-ladder options are eligible for this pattern, prefer the
    ladder-rank-0 rung as the safest starting point. Ties break
    alphabetically by exercise_id."""
    standalone = [e for e in pool if not e.get("ladder_group")]
    if standalone:
        return sorted(standalone, key=lambda e: e["exercise_id"])[0]
    rank_zero = [e for e in pool if e.get("ladder_rank") == 0]
    candidates = rank_zero if rank_zero else pool
    return sorted(candidates, key=lambda e: e["exercise_id"])[0]


def generate_program(exercises: list, equipment_profile: list, constraints: list, level: str,
                      days_per_week: int, session_minutes: int, block_weeks: int, created: str,
                      goal: str = "general_strength") -> Program:
    """Assemble a program directly from the eligible exercise pool. Used when
    no curated template fits the user's equipment or active constraints, or
    when the user explicitly asks to remix.

    Generated loaded exercises are left with load_value=None for week 1 --
    the user fills in a starting weight by feel (leave 2+ reps in reserve)
    rather than the generator guessing a one-size-fits-all number.
    """
    eligible = exercises_mod.filter_exercises(exercises, equipment_profile, constraints)
    grouped = exercises_mod.group_by_pattern(eligible)

    representatives = {}
    for pattern in PATTERN_ORDER:
        pool = grouped.get(pattern, [])
        if pool:
            representatives[pattern] = _pick_representative(pool)

    patterns_with_options = [p for p in PATTERN_ORDER if p in representatives]
    per_slot_weeks = []
    for day in range(1, days_per_week + 1):
        slot_series = []
        for pattern in patterns_with_options[:5]:
            ex = representatives[pattern]
            if ex.get("ladder_group"):
                entry = {"ladder_group": ex["ladder_group"], "sets": DEFAULT_SETS,
                         "weeks_per_rung": DEFAULT_WEEKS_PER_RUNG, "tempo": "2-0-2", "rest": "60s",
                         "notes": ex.get("notes", "")}
                slot_series.append(_build_ladder_exercise(entry, exercises, block_weeks))
            else:
                entry = {"exercise_id": ex["exercise_id"], "sets": DEFAULT_SETS,
                         "reps_low": DEFAULT_REPS_LOW, "reps_high": DEFAULT_REPS_HIGH,
                         "rep_step": DEFAULT_REP_STEP, "load_value": None,
                         "load_increment": DEFAULT_LOAD_INCREMENT, "tempo": "2-0-2", "rest": "90s",
                         "notes": ex.get("notes", "")}
                slot_series.append(_build_loaded_exercise(entry, exercises, block_weeks, "double-progression"))
        per_slot_weeks.append((day, f"Session {day}", slot_series))

    weeks = []
    for week_number in range(1, block_weeks + 1):
        sessions = []
        for day, label, slot_series in per_slot_weeks:
            week_exercises = [series[week_number - 1] for series in slot_series]
            sessions.append(Session(day=day, label=label, exercises=week_exercises))
        weeks.append(Week(number=week_number, sessions=sessions))

    meta = ProgramMeta(
        level=level, goal=goal, days_per_week=days_per_week, session_minutes=session_minutes,
        equipment_profile=list(equipment_profile), constraints=list(constraints), created=created,
        source="generated",
    )
    return Program(
        meta=meta, progression=Progression(model="double-progression", block_weeks=block_weeks), weeks=weeks
    )
