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

    # dumbbell alone fully satisfies db_goblet_squat's equipment requirement,
    # so a nonzero count here would only be prevented by constraint
    # filtering (the "grip" flag) -- this isolates the constraint check from
    # the equipment-subset check, unlike the pull_up_bar case above.
    dumbbell = next(r for r in ranked if r["equipment_id"] == "dumbbell")
    assert dumbbell["unlocks_exercise_count"] == 0


def test_find_equipment_bundles_surfaces_pairs_no_single_purchase_can_unlock():
    ranked = advisor.rank_equipment_gaps(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=[], excluded_constraints=[]
    )
    # Neither half of the pair scores anything on its own...
    for eid in ("pull_up_bar", "resistance_band"):
        assert next(r for r in ranked if r["equipment_id"] == eid)["unlocks_exercise_count"] == 0

    # ...but together they unlock the band-assisted pull-up.
    bundles = advisor.find_equipment_bundles(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=[], excluded_constraints=[]
    )
    pair = next(b for b in bundles if b["equipment_ids"] == ["pull_up_bar", "resistance_band"])
    assert pair["unlocks_exercises"] == ["pullup_band_assisted"]
    assert pair["unlocks_patterns"] == ["pull"]
    assert pair["approx_cost_usd"] == 60


def test_find_equipment_bundles_skips_partly_owned_and_constraint_ruled_out_pairs():
    owned = advisor.find_equipment_bundles(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=["pull_up_bar"],
        excluded_constraints=[],
    )
    assert owned == []  # one item missing -> the single-item ranking covers it

    constrained = advisor.find_equipment_bundles(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=[],
        excluded_constraints=["grip"],
    )
    assert constrained == []


def test_real_catalog_surfaces_the_pullup_bundle():
    exercises = exercises_mod.load_exercises()
    catalog = advisor.load_equipment_catalog()
    bundles = advisor.find_equipment_bundles(exercises, catalog, [], [])
    assert any(
        b["equipment_ids"] == ["pull_up_bar", "resistance_band"]
        and "pullup_band_assisted" in b["unlocks_exercises"]
        for b in bundles
    )


def test_thin_or_missing_patterns_flags_uncovered_patterns():
    thin = advisor.thin_or_missing_patterns(SAMPLE_EXERCISES, equipment_ids=[], excluded_constraints=[])
    assert "pull" in thin


def test_real_catalog_and_exercises_produce_rankings():
    exercises = exercises_mod.load_exercises()
    catalog = advisor.load_equipment_catalog()
    ranked = advisor.rank_equipment_gaps(exercises, catalog, owned_equipment_ids=[], excluded_constraints=[])
    assert len(ranked) == len(catalog)
    assert ranked[0]["score"] >= ranked[-1]["score"]
