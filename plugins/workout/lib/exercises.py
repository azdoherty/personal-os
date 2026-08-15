"""Exercise database loading and equipment/constraint-aware filtering."""
from __future__ import annotations

import json
from pathlib import Path

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"


def load_exercises(path=None) -> list:
    """Load the exercise DB from references/exercises.json (or an override path)."""
    path = path or (REFERENCES_DIR / "exercises.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_eligible(exercise: dict, equipment_ids: set, excluded_constraints: set) -> bool:
    """An exercise is eligible if every piece of required equipment is owned
    and none of its constraint flags are in the excluded set."""
    required = set(exercise.get("equipment_required", []))
    if not required.issubset(equipment_ids):
        return False
    flags = set(exercise.get("constraint_flags", []))
    if flags & excluded_constraints:
        return False
    return True


def filter_exercises(exercises: list, equipment_ids, excluded_constraints) -> list:
    equipment_ids = set(equipment_ids)
    excluded_constraints = set(excluded_constraints)
    return [e for e in exercises if is_eligible(e, equipment_ids, excluded_constraints)]


def group_by_pattern(exercises: list) -> dict:
    grouped: dict = {}
    for e in exercises:
        grouped.setdefault(e["movement_pattern"], []).append(e)
    return grouped


def ladder_for_group(exercises: list, ladder_group: str) -> list:
    """Return the exercises in a ladder group, ordered easiest -> hardest."""
    rungs = [e for e in exercises if e.get("ladder_group") == ladder_group]
    return sorted(rungs, key=lambda e: e["ladder_rank"])


def find_by_id(exercises: list, exercise_id: str) -> dict:
    for e in exercises:
        if e["exercise_id"] == exercise_id:
            return e
    raise KeyError(f"no exercise with id {exercise_id!r}")
