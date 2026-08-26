import pytest

import exercises as ex_mod


SAMPLE = [
    {"exercise_id": "a", "name": "A", "movement_pattern": "squat",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "sq", "ladder_rank": 0,
     "default_reps": "10-15", "notes": ""},
    {"exercise_id": "b", "name": "B", "movement_pattern": "squat",
     "equipment_required": ["dumbbell"], "constraint_flags": ["grip"], "ladder_group": None,
     "ladder_rank": None, "default_reps": "8-12", "notes": ""},
    {"exercise_id": "c", "name": "C", "movement_pattern": "push",
     "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push",
     "ladder_rank": 0, "default_reps": "8-12", "notes": ""},
]


def test_filter_excludes_missing_equipment():
    result = ex_mod.filter_exercises(SAMPLE, equipment_ids=[], excluded_constraints=[])
    ids = {e["exercise_id"] for e in result}
    assert ids == {"a", "c"}


def test_filter_excludes_constraint_flagged_exercises():
    result = ex_mod.filter_exercises(SAMPLE, equipment_ids=["dumbbell"], excluded_constraints=["arm-load"])
    ids = {e["exercise_id"] for e in result}
    assert ids == {"a", "b"}


def test_filter_arm_free_leaves_only_arm_free_options():
    result = ex_mod.filter_exercises(
        SAMPLE, equipment_ids=["dumbbell"], excluded_constraints=["grip", "arm-load"]
    )
    ids = {e["exercise_id"] for e in result}
    assert ids == {"a"}


def test_group_by_pattern():
    grouped = ex_mod.group_by_pattern(SAMPLE)
    assert len(grouped["squat"]) == 2
    assert len(grouped["push"]) == 1


def test_ladder_for_group_orders_by_rank():
    exercises = SAMPLE + [
        {"exercise_id": "a2", "name": "A2", "movement_pattern": "squat", "equipment_required": [],
         "constraint_flags": [], "ladder_group": "sq", "ladder_rank": 1, "default_reps": "8-10",
         "notes": ""},
    ]
    ladder = ex_mod.ladder_for_group(exercises, "sq")
    assert [e["exercise_id"] for e in ladder] == ["a", "a2"]


def test_eligible_ladder_keeps_only_rungs_the_user_can_actually_do():
    ladder = [
        {"exercise_id": "r0", "movement_pattern": "pull", "equipment_required": [],
         "constraint_flags": [], "ladder_group": "mixed", "ladder_rank": 0},
        {"exercise_id": "r1", "movement_pattern": "pull", "equipment_required": ["pull_up_bar"],
         "constraint_flags": [], "ladder_group": "mixed", "ladder_rank": 1},
        {"exercise_id": "r2", "movement_pattern": "pull", "equipment_required": [],
         "constraint_flags": ["grip"], "ladder_group": "mixed", "ladder_rank": 2},
    ]
    assert [e["exercise_id"] for e in ex_mod.eligible_ladder(ladder, "mixed", [], [])] == ["r0", "r2"]
    assert [e["exercise_id"] for e in
            ex_mod.eligible_ladder(ladder, "mixed", ["pull_up_bar"], ["grip"])] == ["r0", "r1"]
    assert [e["exercise_id"] for e in
            ex_mod.eligible_ladder(ladder, "mixed", [], ["grip", "arm-load"])] == ["r0"]


def test_eligible_ladder_is_empty_when_no_rung_qualifies():
    ladder = [
        {"exercise_id": "r0", "movement_pattern": "pull", "equipment_required": ["barbell"],
         "constraint_flags": [], "ladder_group": "mixed", "ladder_rank": 0},
    ]
    assert ex_mod.eligible_ladder(ladder, "mixed", [], []) == []


@pytest.mark.parametrize("raw,expected", [
    ("8-12", (8, 12, "")),
    ("5", (5, 5, "")),
    ("3-5 trips", (3, 5, "trips")),
    ("8-10 / leg", (8, 10, "/ leg")),
    ("30-45s", (30, 45, "s")),
    ("AMRAP", None),
    ("", None),
])
def test_parse_default_reps(raw, expected):
    assert ex_mod.parse_default_reps(raw) == expected


def test_every_shipped_exercise_has_parseable_default_reps():
    for e in ex_mod.load_exercises():
        assert ex_mod.parse_default_reps(e["default_reps"]) is not None, e["exercise_id"]


def test_find_by_id_raises_for_unknown():
    with pytest.raises(KeyError):
        ex_mod.find_by_id(SAMPLE, "nonexistent")


def test_real_exercise_db_loads_and_has_expected_shape():
    real = ex_mod.load_exercises()
    assert len(real) >= 20
    ids = {e["exercise_id"] for e in real}
    assert "bodyweight_squat" in ids
    assert "weighted_vest_split_squat" in ids
    for e in real:
        assert e["movement_pattern"] in {"squat", "hinge", "push", "pull", "carry", "core"}


def test_every_ladder_group_is_equipment_and_pattern_uniform_across_rungs():
    """generator.py credits a ladder slot with the union of every eligible
    rung's equipment/pattern, but progression only ever reaches ONE rung per
    week. That's only safe if every rung in a group shares the same
    equipment_required/constraint_flags/movement_pattern. If this ever fails,
    the per-pattern equipment guard (lib/generator.py) needs to be reworked
    to credit only the reachable rung, not the whole group -- see the
    round-3/round-4 review history on template equipment matching.
    """
    real = ex_mod.load_exercises()
    ladder_groups = {}
    for e in real:
        group = e.get("ladder_group")
        if group:
            ladder_groups.setdefault(group, []).append(e)

    for group_name, rungs in ladder_groups.items():
        equipment_sets = {tuple(sorted(r.get("equipment_required", []))) for r in rungs}
        constraint_sets = {tuple(sorted(r.get("constraint_flags", []))) for r in rungs}
        patterns = {r["movement_pattern"] for r in rungs}
        assert len(equipment_sets) == 1, (
            f"ladder group {group_name!r} has rungs requiring different equipment: "
            f"{equipment_sets}"
        )
        assert len(constraint_sets) == 1, (
            f"ladder group {group_name!r} has rungs with different constraint_flags: "
            f"{constraint_sets}"
        )
        assert len(patterns) == 1, (
            f"ladder group {group_name!r} spans multiple movement patterns: {patterns}"
        )


def test_bucket_by_sub_category_uses_the_tag_when_present():
    exercises = [
        {"exercise_id": "dead_bug", "movement_pattern": "core", "sub_category": "anti_extension"},
        {"exercise_id": "bird_dog", "movement_pattern": "core", "sub_category": "anti_rotation"},
        {"exercise_id": "plank", "movement_pattern": "core", "sub_category": "anti_extension"},
    ]
    buckets = ex_mod.bucket_by_sub_category(exercises)
    assert set(buckets) == {"anti_extension", "anti_rotation"}
    assert {e["exercise_id"] for e in buckets["anti_extension"]} == {"dead_bug", "plank"}
    assert {e["exercise_id"] for e in buckets["anti_rotation"]} == {"bird_dog"}


def test_bucket_by_sub_category_falls_back_to_movement_pattern_when_untagged():
    exercises = [
        {"exercise_id": "box_squat", "movement_pattern": "squat"},
        {"exercise_id": "db_goblet_squat", "movement_pattern": "squat"},
        {"exercise_id": "glute_bridge", "movement_pattern": "hinge"},
    ]
    buckets = ex_mod.bucket_by_sub_category(exercises)
    assert set(buckets) == {"squat", "hinge"}
    assert len(buckets["squat"]) == 2


def test_bucket_by_sub_category_mixes_tagged_and_untagged_within_one_pattern():
    exercises = [
        {"exercise_id": "table_inverted_row", "movement_pattern": "pull", "sub_category": "biceps"},
        {"exercise_id": "db_bent_over_row", "movement_pattern": "pull"},
    ]
    buckets = ex_mod.bucket_by_sub_category(exercises)
    assert set(buckets) == {"biceps", "pull"}


def test_real_core_exercises_span_all_four_sub_categories():
    real = ex_mod.load_exercises()
    core = [e for e in real if e["movement_pattern"] == "core"]
    buckets = ex_mod.bucket_by_sub_category(core)
    assert set(buckets) == {"anti_extension", "anti_rotation", "flexion", "hip_flexor_endurance"}
