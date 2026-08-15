import advisor
import exercises as exercises_mod


SAMPLE_EXERCISES = [
    {"exercise_id": "bodyweight_squat", "movement_pattern": "squat", "equipment_required": [],
     "constraint_flags": []},
    {"exercise_id": "db_goblet_squat", "movement_pattern": "squat", "equipment_required": ["dumbbell"],
     "constraint_flags": ["grip"]},
    {"exercise_id": "table_inverted_row", "movement_pattern": "pull",
     "equipment_required": ["sturdy_table"], "constraint_flags": ["arm-load", "grip"]},
    {"exercise_id": "pullup_band_assisted", "movement_pattern": "pull",
     "equipment_required": ["pull_up_bar", "resistance_band"], "constraint_flags": ["arm-load", "grip"]},
]

SAMPLE_CATALOG = [
    {"equipment_id": "dumbbell", "name": "Dumbbells", "cost_tier": "medium", "space_tier": "small",
     "approx_cost_usd": 250},
    {"equipment_id": "pull_up_bar", "name": "Pull-Up Bar", "cost_tier": "low", "space_tier": "small",
     "approx_cost_usd": 30},
    {"equipment_id": "resistance_band", "name": "Resistance Band", "cost_tier": "low",
     "space_tier": "small", "approx_cost_usd": 30},
]


def test_pattern_coverage_counts_eligible_exercises_per_pattern():
    coverage = advisor.pattern_coverage(SAMPLE_EXERCISES, equipment_ids=[], excluded_constraints=[])
    assert coverage["squat"] == 1
    assert coverage.get("pull", 0) == 0


def test_rank_equipment_gaps_orders_by_unlock_score():
    ranked = advisor.rank_equipment_gaps(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=[], excluded_constraints=[]
    )
    ids = [r["equipment_id"] for r in ranked]
    assert "dumbbell" in ids
    dumbbell = next(r for r in ranked if r["equipment_id"] == "dumbbell")
    assert dumbbell["unlocks_exercise_count"] == 1
    assert dumbbell["unlocks_patterns"] == ["squat"]


def test_rank_equipment_gaps_excludes_already_owned_equipment():
    ranked = advisor.rank_equipment_gaps(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=["dumbbell"], excluded_constraints=[]
    )
    assert all(r["equipment_id"] != "dumbbell" for r in ranked)


def test_rank_equipment_gaps_respects_active_constraints():
    ranked = advisor.rank_equipment_gaps(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=[],
        excluded_constraints=["arm-load", "grip"],
    )
    pull_up = next(r for r in ranked if r["equipment_id"] == "pull_up_bar")
    assert pull_up["unlocks_exercise_count"] == 0


def test_thin_or_missing_patterns_flags_uncovered_patterns():
    thin = advisor.thin_or_missing_patterns(SAMPLE_EXERCISES, equipment_ids=[], excluded_constraints=[])
    assert "pull" in thin


def test_real_catalog_and_exercises_produce_rankings():
    exercises = exercises_mod.load_exercises()
    catalog = advisor.load_equipment_catalog()
    ranked = advisor.rank_equipment_gaps(exercises, catalog, owned_equipment_ids=[], excluded_constraints=[])
    assert len(ranked) == len(catalog)
    assert ranked[0]["score"] >= ranked[-1]["score"]
