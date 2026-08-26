import pytest

import progression as prog_mod


def test_apply_linear_holds_for_first_week():
    cfg = {"sets": 3, "reps": "5", "load_value": 20.0, "increment": 5.0, "increment_every_weeks": 2}
    week1 = prog_mod.apply_linear(cfg, 1)
    assert week1["load_value"] == 20.0


def test_apply_linear_increments_on_schedule():
    cfg = {"sets": 3, "reps": "5", "load_value": 20.0, "increment": 5.0, "increment_every_weeks": 2}
    assert prog_mod.apply_linear(cfg, 3)["load_value"] == 25.0
    assert prog_mod.apply_linear(cfg, 5)["load_value"] == 30.0


def test_double_progression_climbs_reps_then_resets_with_load_bump():
    cfg = {
        "sets": 3, "reps_low": 8, "reps_high": 10, "rep_step": 1,
        "load_value": 15.0, "load_increment": 5.0,
    }
    week1 = prog_mod.apply_double_progression(cfg, 1)
    week3 = prog_mod.apply_double_progression(cfg, 3)
    week4 = prog_mod.apply_double_progression(cfg, 4)
    assert week1["reps"] == "8" and week1["load_value"] == 15.0
    assert week3["reps"] == "10" and week3["load_value"] == 15.0
    assert week4["reps"] == "8" and week4["load_value"] == 20.0


def test_double_progression_handles_unset_load():
    cfg = {"sets": 3, "reps_low": 8, "reps_high": 9, "rep_step": 1, "load_value": None, "load_increment": 5.0}
    week1 = prog_mod.apply_double_progression(cfg, 1)
    week3 = prog_mod.apply_double_progression(cfg, 3)
    assert week1["load_value"] is None
    assert week3["load_value"] is None


def test_variation_ladder_climbs_one_rung_per_interval():
    ladder = [
        {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "default_reps": "8-12"},
        {"exercise_id": "pushup", "name": "Push-Up", "default_reps": "10-15"},
        {"exercise_id": "decline_pushup", "name": "Decline Push-Up", "default_reps": "8-12"},
    ]
    cfg = {"sets": 3, "weeks_per_rung": 2}
    assert prog_mod.apply_variation_ladder(cfg, 1, ladder)["exercise_id"] == "incline_pushup"
    assert prog_mod.apply_variation_ladder(cfg, 3, ladder)["exercise_id"] == "pushup"
    assert prog_mod.apply_variation_ladder(cfg, 5, ladder)["exercise_id"] == "decline_pushup"


def test_variation_ladder_caps_at_top_rung():
    ladder = [
        {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "default_reps": "8-12"},
        {"exercise_id": "pushup", "name": "Push-Up", "default_reps": "10-15"},
    ]
    cfg = {"sets": 3, "weeks_per_rung": 2}
    assert prog_mod.apply_variation_ladder(cfg, 100, ladder)["exercise_id"] == "pushup"


def test_variation_ladder_notes_come_from_the_active_rung_not_a_static_slot_note():
    ladder = [
        {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "default_reps": "8-12",
         "notes": "Hands elevated."},
        {"exercise_id": "pushup", "name": "Push-Up", "default_reps": "10-15",
         "notes": "Hands on the floor."},
    ]
    cfg = {"sets": 3, "weeks_per_rung": 2}
    week1 = prog_mod.apply_variation_ladder(cfg, 1, ladder)
    week3 = prog_mod.apply_variation_ladder(cfg, 3, ladder)
    assert week1["notes"] == "Hands elevated."
    assert week3["notes"] == "Hands on the floor."


def test_generate_block_dispatches_by_model():
    cfg = {"sets": 3, "reps_low": 8, "reps_high": 9, "rep_step": 1, "load_value": 10.0, "load_increment": 5.0}
    weeks = prog_mod.generate_block(cfg, block_weeks=4, model="double-progression")
    assert len(weeks) == 4


def test_generate_block_variation_ladder_requires_ladder():
    cfg = {"sets": 3, "weeks_per_rung": 2}
    with pytest.raises(ValueError):
        prog_mod.generate_block(cfg, block_weeks=4, model="variation-ladder")


def test_generate_block_unknown_model_raises():
    with pytest.raises(ValueError):
        prog_mod.generate_block({}, block_weeks=1, model="not-a-model")
