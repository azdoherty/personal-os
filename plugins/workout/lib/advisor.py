"""Equipment gap analysis: given what the user owns (and any active
constraints), rank equipment_catalog items by how much new eligible-exercise
value they'd unlock.
"""
from __future__ import annotations

import json
from pathlib import Path

from model import MOVEMENT_PATTERNS
import exercises as exercises_mod

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"

COST_WEIGHT = {"none": 4, "low": 3, "medium": 2, "high": 1}


def load_equipment_catalog(path=None) -> list:
    path = path or (REFERENCES_DIR / "equipment.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pattern_coverage(exercises: list, equipment_ids, excluded_constraints) -> dict:
    """Return {pattern: eligible_exercise_count} for every movement pattern."""
    eligible = exercises_mod.filter_exercises(exercises, equipment_ids, excluded_constraints)
    grouped = exercises_mod.group_by_pattern(eligible)
    return {pattern: len(items) for pattern, items in grouped.items()}


def rank_equipment_gaps(exercises: list, catalog: list, owned_equipment_ids, excluded_constraints) -> list:
    """Rank equipment the user doesn't yet own by how much new value adding
    it would unlock: how many currently-ineligible exercises become eligible,
    weighted by cost tier (cheaper + more unlocks ranks higher), with
    constraint-flagged exercises excluded from the unlock count (an item that
    only unlocks exercises the user's constraints rule out isn't actually
    useful to them right now).
    """
    owned = set(owned_equipment_ids)
    excluded = set(excluded_constraints)
    currently_eligible_ids = {
        e["exercise_id"] for e in exercises_mod.filter_exercises(exercises, owned, excluded)
    }

    results = []
    for item in catalog:
        equipment_id = item["equipment_id"]
        if equipment_id in owned:
            continue
        with_item = owned | {equipment_id}
        newly_eligible = [
            e for e in exercises_mod.filter_exercises(exercises, with_item, excluded)
            if e["exercise_id"] not in currently_eligible_ids
        ]
        unlocked_patterns = sorted({e["movement_pattern"] for e in newly_eligible})
        score = len(newly_eligible) * COST_WEIGHT.get(item["cost_tier"], 1)
        results.append({
            "equipment_id": equipment_id,
            "name": item["name"],
            "cost_tier": item["cost_tier"],
            "space_tier": item["space_tier"],
            "approx_cost_usd": item["approx_cost_usd"],
            "unlocks_exercise_count": len(newly_eligible),
            "unlocks_patterns": unlocked_patterns,
            "score": score,
        })
    return sorted(results, key=lambda r: r["score"], reverse=True)


def thin_or_missing_patterns(exercises: list, equipment_ids, excluded_constraints, threshold: int = 2) -> list:
    """Patterns with fewer than `threshold` eligible exercises -- worth
    flagging even before ranking specific equipment."""
    coverage = pattern_coverage(exercises, equipment_ids, excluded_constraints)
    return [p for p in MOVEMENT_PATTERNS if coverage.get(p, 0) < threshold]
