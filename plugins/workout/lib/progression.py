"""Deterministic progression: given an exercise's starting configuration and
a block length, compute the sets/reps/load for every week of the block up
front (v1 is one-shot -- see model.py's log fields for the future adaptive
hook). Three models, matching model.PROGRESSION_MODELS.
"""
from __future__ import annotations

from model import PROGRESSION_MODELS


def apply_linear(exercise_cfg: dict, week_number: int) -> dict:
    """Fixed load increase every `increment_every_weeks` weeks."""
    increment = exercise_cfg.get("increment", 5.0)
    increment_every = exercise_cfg.get("increment_every_weeks", 1)
    base_load = exercise_cfg["load_value"]
    steps = (week_number - 1) // increment_every
    load = base_load + steps * increment
    return {
        "sets": exercise_cfg["sets"],
        "reps": exercise_cfg["reps"],
        "load_type": "external",
        "load_value": load,
    }


def apply_double_progression(exercise_cfg: dict, week_number: int) -> dict:
    """Reps climb by `rep_step` each week within [reps_low, reps_high]. On
    reaching reps_high, load increases by `load_increment` and reps reset to
    reps_low. If load_value is None (an unknown starting weight -- the
    generator's fallback case), load stays None throughout and only reps
    progress; the user fills in and tracks their own load by feel.
    """
    reps_low = exercise_cfg["reps_low"]
    reps_high = exercise_cfg["reps_high"]
    rep_step = exercise_cfg.get("rep_step", 1)
    load_increment = exercise_cfg.get("load_increment", 5.0)
    base_load = exercise_cfg.get("load_value")
    span = reps_high - reps_low
    weeks_per_cycle = (span // rep_step) + 1
    cycle_index = (week_number - 1) // weeks_per_cycle
    week_in_cycle = (week_number - 1) % weeks_per_cycle
    reps_current = reps_low + week_in_cycle * rep_step
    load = None if base_load is None else base_load + cycle_index * load_increment
    return {
        "sets": exercise_cfg["sets"],
        "reps": f"{reps_current}",
        "load_type": "external",
        "load_value": load,
    }


def apply_variation_ladder(exercise_cfg: dict, week_number: int, ladder: list) -> dict:
    """Climb one rung of `ladder` (ordered easiest -> hardest, sharing a
    ladder_group) every `weeks_per_rung` weeks, capped at the top rung.
    """
    weeks_per_rung = exercise_cfg.get("weeks_per_rung", 2)
    rung_index = min((week_number - 1) // weeks_per_rung, len(ladder) - 1)
    rung = ladder[rung_index]
    return {
        "exercise_id": rung["exercise_id"],
        "name": rung["name"],
        "sets": exercise_cfg["sets"],
        "reps": rung["default_reps"],
        "load_type": "bodyweight",
        "load_value": None,
    }


def generate_block(exercise_cfg: dict, block_weeks: int, model: str, ladder=None) -> list:
    """Return one entry per week (1..block_weeks) for this exercise."""
    if model not in PROGRESSION_MODELS:
        raise ValueError(f"unknown progression model: {model}")
    weeks = []
    for w in range(1, block_weeks + 1):
        if model == "linear":
            weeks.append(apply_linear(exercise_cfg, w))
        elif model == "double-progression":
            weeks.append(apply_double_progression(exercise_cfg, w))
        elif model == "variation-ladder":
            if not ladder:
                raise ValueError("variation-ladder model requires a ladder")
            weeks.append(apply_variation_ladder(exercise_cfg, w, ladder))
    return weeks
