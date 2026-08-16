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
MINUTES_PER_SLOT = 10
MIN_SLOTS = 2
MAX_SLOTS = len(PATTERN_ORDER)


class LadderUnavailable(ValueError):
    """No rung of a ladder group is eligible for this equipment/constraints."""


def _slot_pattern(entry: dict, exercises: list) -> str:
    """The movement pattern a template slot trains, regardless of whether the
    user can currently do any of its options. Empty string when the slot's
    ladder group isn't in the exercise DB at all."""
    if "ladder_group" in entry:
        rungs = exercises_mod.ladder_for_group(exercises, entry["ladder_group"])
        return rungs[0]["movement_pattern"] if rungs else ""
    return exercises_mod.find_by_id(exercises, entry["exercise_id"])["movement_pattern"]


def template_buildability(template: dict, exercises: list, equipment_profile, constraints) -> dict:
    """Decide whether a curated template can be built for this user, and how.

    Mirrors exactly what `build_program_from_template` does:

    * A **fixed** exercise slot must be eligible outright (equipment owned,
      no excluded constraint flag). If it isn't, the template is rejected --
      swapping a hand-picked lift for something else is the generator's job,
      not the template builder's.
    * A **ladder** slot is built from the rungs the user is eligible for. If
      no rung is eligible, the slot is dropped -- but only when nothing else
      in the user's eligible pool trains that pattern either. If the pool
      *does* cover the pattern (e.g. they own a pull-up bar this bodyweight
      template never mentions), the template is rejected so the generator can
      use what they actually own.
    * A session left with zero exercises means the template really doesn't
      fit -- reject it.

    Returns {"buildable": bool, "reason": str|None, "skipped_patterns": [...]}.
    """
    equipment = set(equipment_profile)
    excluded = set(constraints)
    pool_patterns = {
        e["movement_pattern"]
        for e in exercises_mod.filter_exercises(exercises, equipment, excluded)
    }
    skipped = []
    for session in template["sessions"]:
        kept = 0
        for entry in session["exercises"]:
            if "ladder_group" in entry:
                if exercises_mod.eligible_ladder(exercises, entry["ladder_group"], equipment, excluded):
                    kept += 1
                else:
                    pattern = _slot_pattern(entry, exercises)
                    if pattern in pool_patterns:
                        return {
                            "buildable": False,
                            "reason": (
                                f"you own equipment for {pattern} work that this template's "
                                f"{pattern} progression can't use"
                            ),
                            "skipped_patterns": [],
                        }
                    if pattern and pattern not in skipped:
                        skipped.append(pattern)
            else:
                ex = exercises_mod.find_by_id(exercises, entry["exercise_id"])
                if not exercises_mod.is_eligible(ex, equipment, excluded):
                    return {
                        "buildable": False,
                        "reason": (
                            f"its {ex['name']} slot needs equipment you don't have "
                            f"or conflicts with your constraints"
                        ),
                        "skipped_patterns": [],
                    }
                kept += 1
        if kept == 0:
            return {
                "buildable": False,
                "reason": f"day {session['day']} would have no exercises left",
                "skipped_patterns": skipped,
            }
    return {"buildable": True, "reason": None, "skipped_patterns": skipped}


def template_is_constraint_compatible(template: dict, exercises: list, excluded_constraints,
                                       equipment_profile=None) -> bool:
    """Boolean view of `template_buildability`. `equipment_profile=None`
    means "don't check equipment", i.e. constraint compatibility only."""
    if equipment_profile is None:
        equipment_profile = _all_equipment_ids(exercises)
    return template_buildability(template, exercises, equipment_profile, excluded_constraints)["buildable"]


def _all_equipment_ids(exercises: list) -> set:
    ids = set()
    for e in exercises:
        ids.update(e.get("equipment_required", []))
    return ids


def _build_ladder_exercise(entry: dict, exercises: list, block_weeks: int,
                            equipment_profile, constraints) -> list:
    ladder = exercises_mod.eligible_ladder(
        exercises, entry["ladder_group"], equipment_profile, constraints
    )
    if not ladder:
        raise LadderUnavailable(
            f"no rung of ladder group {entry['ladder_group']!r} is eligible for "
            f"equipment={sorted(equipment_profile)} constraints={sorted(constraints)}"
        )
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
    # A rep unit other than "reps" (e.g. "trips", "/ leg") comes from the
    # exercise DB's default_reps and has to survive onto the printed program,
    # or "3 sets of 8" of a sled push reads as nonsense.
    suffix = entry.get("reps_suffix", "")

    def as_reps(value) -> str:
        return f"{value} {suffix}".strip() if suffix else f"{value}"

    def spoken(value) -> str:
        return f"{value} {suffix or 'reps'}".strip()

    if model_name == "double-progression":
        rule = (
            f"Add a rep each week; at {spoken(entry['reps_high'])} for all sets, "
            f"add {entry['load_increment']}lb and reset to {spoken(entry['reps_low'])}."
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
            movement_pattern=ex_meta["movement_pattern"], sets=entry["sets"],
            reps=as_reps(step["reps"]),
            load=LoadSpec(type="external", value=step["load_value"], progression_rule=rule),
            tempo=entry["tempo"], rest=entry["rest"], notes=entry.get("notes", ""),
        ))
    return result


def build_program_from_template(template: dict, exercises: list, equipment_profile: list,
                                 constraints: list, created: str, session_minutes=None) -> Program:
    """Build a curated template into a concrete Program.

    Ladder slots are filtered to the rungs this user can actually do; a slot
    with no eligible rung is dropped (see `template_buildability`, which
    decides up front whether dropping it is acceptable). `session_minutes`
    overrides the template's own value when the caller supplies one.
    """
    block_weeks = template["block_weeks"]
    model_name = template["progression_model"]

    per_slot_weeks = []
    for session in template["sessions"]:
        slot_series = []
        for entry in session["exercises"]:
            if "ladder_group" in entry:
                try:
                    slot_series.append(_build_ladder_exercise(
                        entry, exercises, block_weeks, equipment_profile, constraints))
                except LadderUnavailable:
                    continue
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
        session_minutes=session_minutes or template["session_minutes"],
        equipment_profile=list(equipment_profile),
        constraints=list(constraints), created=created, source=template["template_id"],
    )
    return Program(meta=meta, progression=Progression(model=model_name, block_weeks=block_weeks), weeks=weeks)


def _pick_representative(pool: list) -> dict:
    """Deterministic pick: prefer a standalone, directly-loadable exercise
    (not part of a bodyweight ladder) when one is eligible, since that lets
    the fallback program actually use equipment the user owns. Among
    standalones, prefer the most *tailored* option -- the one using the most
    of the user's owned equipment (everything in `pool` is already eligible,
    so more required equipment means more of their gear put to work). This
    mirrors `templates.match_template`'s "most equipment wins" tie-break.
    When only bodyweight-ladder options are eligible for this pattern, prefer
    the ladder-rank-0 rung as the safest starting point. Ties break
    alphabetically by exercise_id."""
    standalone = [e for e in pool if not e.get("ladder_group")]
    if standalone:
        return sorted(
            standalone,
            key=lambda e: (-len(e.get("equipment_required", [])), e["exercise_id"]),
        )[0]
    rank_zero = [e for e in pool if e.get("ladder_rank") == 0]
    candidates = rank_zero if rank_zero else pool
    return sorted(candidates, key=lambda e: e["exercise_id"])[0]


def slots_per_session(session_minutes: int) -> int:
    """How many exercise slots fit in a session. Roughly one slot per
    `MINUTES_PER_SLOT` minutes of training (a working set plus its rest,
    times ~3 sets), floored at MIN_SLOTS so a very short session still
    trains something and capped at one slot per movement pattern."""
    return max(MIN_SLOTS, min(MAX_SLOTS, int(session_minutes) // MINUTES_PER_SLOT))


def _reps_from_db(exercise: dict):
    """(reps_low, reps_high, suffix) for a generated standalone slot, taken
    from the exercise DB's own `default_reps` rather than a one-size-fits-all
    8-12 -- a sled push is programmed in trips, not reps. Falls back to the
    8-12 default when `default_reps` has no extractable numbers."""
    parsed = exercises_mod.parse_default_reps(exercise.get("default_reps", ""))
    if parsed is None:
        return DEFAULT_REPS_LOW, DEFAULT_REPS_HIGH, ""
    return parsed


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
        for pattern in patterns_with_options[:slots_per_session(session_minutes)]:
            ex = representatives[pattern]
            if ex.get("ladder_group"):
                entry = {"ladder_group": ex["ladder_group"], "sets": DEFAULT_SETS,
                         "weeks_per_rung": DEFAULT_WEEKS_PER_RUNG, "tempo": "2-0-2", "rest": "60s",
                         "notes": ex.get("notes", "")}
                slot_series.append(_build_ladder_exercise(
                    entry, exercises, block_weeks, equipment_profile, constraints))
            else:
                reps_low, reps_high, reps_suffix = _reps_from_db(ex)
                entry = {"exercise_id": ex["exercise_id"], "sets": DEFAULT_SETS,
                         "reps_low": reps_low, "reps_high": reps_high, "reps_suffix": reps_suffix,
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
