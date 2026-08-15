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
