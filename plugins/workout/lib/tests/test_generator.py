import pytest

import model
import exercises as exercises_mod
import templates as templates_mod
import generator as gen_mod


SAMPLE_EXERCISES = [
    {"exercise_id": "box_squat", "name": "Box Squat", "movement_pattern": "squat",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
     "ladder_rank": 0, "default_reps": "10-15", "notes": ""},
    {"exercise_id": "bodyweight_squat", "name": "Bodyweight Squat", "movement_pattern": "squat",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
     "ladder_rank": 1, "default_reps": "12-15", "notes": ""},
    {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "movement_pattern": "push",
     "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push_bw",
     "ladder_rank": 0, "default_reps": "8-12", "notes": ""},
    {"exercise_id": "db_goblet_squat", "name": "DB Goblet Squat", "movement_pattern": "squat",
     "equipment_required": ["dumbbell"], "constraint_flags": ["grip"], "ladder_group": None,
     "ladder_rank": None, "default_reps": "8-12", "notes": ""},
]

SAMPLE_TEMPLATE = {
    "template_id": "sample", "level": "beginner", "goal": "general_strength",
    "days_per_week": 1, "session_minutes": 20, "required_equipment": [],
    "progression_model": "variation-ladder", "block_weeks": 4,
    "sessions": [
        {"day": 1, "label": "Full Body", "exercises": [
            {"ladder_group": "squat_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2",
             "rest": "60s", "notes": ""},
            {"ladder_group": "push_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2",
             "rest": "60s", "notes": ""},
        ]},
    ],
}


def test_build_program_from_template_produces_valid_program():
    program = gen_mod.build_program_from_template(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=[], created="2026-08-15"
    )
    assert model.validate_program(program) == []
    assert len(program.weeks) == 4
    assert program.weeks[0].sessions[0].exercises[0].exercise_id == "box_squat"
    assert program.weeks[2].sessions[0].exercises[0].exercise_id == "bodyweight_squat"


def test_template_rejected_when_a_session_would_be_left_empty():
    push_only = {**SAMPLE_TEMPLATE, "sessions": [
        {"day": 1, "label": "Push", "exercises": [SAMPLE_TEMPLATE["sessions"][0]["exercises"][1]]},
    ]}
    assert gen_mod.template_is_constraint_compatible(push_only, SAMPLE_EXERCISES, {"arm-load"}) is False


def test_template_is_constraint_compatible_true_when_no_conflicting_flags():
    assert gen_mod.template_is_constraint_compatible(SAMPLE_TEMPLATE, SAMPLE_EXERCISES, {"impact"}) is True


def test_unbuildable_ladder_slot_is_dropped_when_nothing_else_covers_the_pattern():
    report = gen_mod.template_buildability(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=["arm-load"]
    )
    assert report["buildable"] is True
    assert report["skipped_patterns"] == ["push"]

    program = gen_mod.build_program_from_template(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=["arm-load"],
        created="2026-08-15",
    )
    patterns = {ex.movement_pattern for w in program.weeks for s in w.sessions for ex in s.exercises}
    assert patterns == {"squat"}
    assert model.validate_program(program) == []


def test_template_rejected_when_the_user_owns_gear_the_template_cannot_use():
    # push_bw is unusable (arm-load), but the pool has an eligible push
    # option this template never mentions -- the generator serves them better.
    pool = SAMPLE_EXERCISES + [
        {"exercise_id": "vest_push", "name": "Vest Push", "movement_pattern": "push",
         "equipment_required": ["weighted_vest"], "constraint_flags": [], "ladder_group": None,
         "ladder_rank": None, "default_reps": "8-12", "notes": ""},
    ]
    report = gen_mod.template_buildability(
        SAMPLE_TEMPLATE, pool, equipment_profile=["weighted_vest"], constraints=["arm-load"]
    )
    assert report["buildable"] is False
    assert "push" in report["reason"]


HETEROGENEOUS_LADDER = [
    {"exercise_id": "rung_free", "name": "Rung Free", "movement_pattern": "pull",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "mixed",
     "ladder_rank": 0, "default_reps": "8-12", "notes": ""},
    {"exercise_id": "rung_bar", "name": "Rung Bar", "movement_pattern": "pull",
     "equipment_required": ["pull_up_bar"], "constraint_flags": [], "ladder_group": "mixed",
     "ladder_rank": 1, "default_reps": "6-10", "notes": ""},
    {"exercise_id": "rung_grippy", "name": "Rung Grippy", "movement_pattern": "pull",
     "equipment_required": [], "constraint_flags": ["grip"], "ladder_group": "mixed",
     "ladder_rank": 2, "default_reps": "6-8", "notes": ""},
]

MIXED_LADDER_TEMPLATE = {
    "template_id": "mixed", "level": "beginner", "goal": "general_strength",
    "days_per_week": 1, "session_minutes": 20, "required_equipment": [],
    "progression_model": "variation-ladder", "block_weeks": 6,
    "sessions": [
        {"day": 1, "label": "Pull", "exercises": [
            {"ladder_group": "mixed", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2",
             "rest": "60s", "notes": ""},
        ]},
    ],
}


def test_ladder_rungs_needing_unowned_equipment_never_reach_the_program():
    program = gen_mod.build_program_from_template(
        MIXED_LADDER_TEMPLATE, HETEROGENEOUS_LADDER, equipment_profile=[], constraints=["grip"],
        created="2026-08-15",
    )
    ids = {ex.exercise_id for w in program.weeks for s in w.sessions for ex in s.exercises}
    assert ids == {"rung_free"}


def test_ladder_rungs_conflicting_with_constraints_never_reach_the_program():
    program = gen_mod.build_program_from_template(
        MIXED_LADDER_TEMPLATE, HETEROGENEOUS_LADDER, equipment_profile=["pull_up_bar"],
        constraints=["grip"], created="2026-08-15",
    )
    ids = {ex.exercise_id for w in program.weeks for s in w.sessions for ex in s.exercises}
    assert ids == {"rung_free", "rung_bar"}
    assert "rung_grippy" not in ids


def test_fully_ineligible_ladder_fails_compatibility_and_raises_rather_than_leaking_a_bad_rung():
    grip_only = [dict(r, constraint_flags=["grip"]) for r in HETEROGENEOUS_LADDER]
    assert gen_mod.template_is_constraint_compatible(
        MIXED_LADDER_TEMPLATE, grip_only, {"grip"}, equipment_profile=["pull_up_bar"]
    ) is False
    with pytest.raises(gen_mod.LadderUnavailable):
        gen_mod._build_ladder_exercise(
            MIXED_LADDER_TEMPLATE["sessions"][0]["exercises"][0], grip_only, 4,
            equipment_profile=["pull_up_bar"], constraints=["grip"],
        )


def test_template_path_honors_the_requested_session_minutes():
    program = gen_mod.build_program_from_template(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=[],
        created="2026-08-15", session_minutes=45,
    )
    assert SAMPLE_TEMPLATE["session_minutes"] == 20
    assert program.meta.session_minutes == 45


def test_template_session_minutes_is_the_default_when_the_caller_says_nothing():
    program = gen_mod.build_program_from_template(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=[],
        created="2026-08-15",
    )
    assert program.meta.session_minutes == 20


def test_generated_session_size_scales_with_the_requested_minutes():
    exercises = exercises_mod.load_exercises()
    short = gen_mod.generate_program(
        exercises, equipment_profile=["dumbbell"], constraints=[], level="beginner",
        days_per_week=1, session_minutes=20, block_weeks=1, created="2026-08-15",
    )
    long = gen_mod.generate_program(
        exercises, equipment_profile=["dumbbell"], constraints=[], level="beginner",
        days_per_week=1, session_minutes=60, block_weeks=1, created="2026-08-15",
    )
    assert len(short.weeks[0].sessions[0].exercises) == 2
    assert len(long.weeks[0].sessions[0].exercises) > 2
    assert short.meta.session_minutes == 20


def test_generated_standalone_reps_come_from_the_exercise_db_not_a_hardcoded_default():
    exercises = exercises_mod.load_exercises()
    program = gen_mod.generate_program(
        exercises, equipment_profile=["sled"], constraints=["grip", "arm-load"], level="beginner",
        days_per_week=1, session_minutes=30, block_weeks=1, created="2026-08-15",
    )
    sled = next(
        ex for w in program.weeks for s in w.sessions for ex in s.exercises
        if ex.exercise_id == "sled_push"
    )
    # sled_push's default_reps is "3-5 trips" -- not 3 sets of 8.
    assert sled.reps == "3 trips"
    assert "5 trips" in sled.load.progression_rule


def test_zero_equipment_user_gets_a_real_program_from_the_curated_template():
    exercises = exercises_mod.load_exercises()
    template = next(
        t for t in templates_mod.load_all_templates() if t["template_id"] == "bodyweight_beginner_3day"
    )
    assert templates_mod.match_template([template], "beginner", [], 3) is template
    report = gen_mod.template_buildability(template, exercises, equipment_profile=[], constraints=[])
    assert report["buildable"] is True
    assert report["skipped_patterns"] == ["pull"]  # no table -> no bodyweight pull option

    program = gen_mod.build_program_from_template(
        template, exercises, equipment_profile=[], constraints=[], created="2026-08-15",
    )
    assert model.validate_program(program) == []
    assert all(s.exercises for w in program.weeks for s in w.sessions)


def test_generate_program_excludes_constrained_patterns():
    program = gen_mod.generate_program(
        SAMPLE_EXERCISES, equipment_profile=["dumbbell"], constraints=["arm-load"], level="beginner",
        days_per_week=1, session_minutes=30, block_weeks=2, created="2026-08-15",
    )
    all_ids = {ex.exercise_id for w in program.weeks for s in w.sessions for ex in s.exercises}
    assert "incline_pushup" not in all_ids
    assert model.validate_program(program) == []


def test_generate_program_picks_ladder_rank_zero_as_starting_point():
    program = gen_mod.generate_program(
        SAMPLE_EXERCISES, equipment_profile=[], constraints=[], level="beginner",
        days_per_week=1, session_minutes=30, block_weeks=1, created="2026-08-15",
    )
    squat_exercise = next(
        ex for w in program.weeks for s in w.sessions for ex in s.exercises
        if ex.movement_pattern == "squat"
    )
    assert squat_exercise.exercise_id == "box_squat"


def test_generate_program_leaves_generated_load_unset_for_user_to_fill_in():
    program = gen_mod.generate_program(
        SAMPLE_EXERCISES, equipment_profile=["dumbbell"], constraints=["arm-load", "impact"],
        level="beginner", days_per_week=1, session_minutes=30, block_weeks=1, created="2026-08-15",
    )
    loaded = [
        ex for w in program.weeks for s in w.sessions for ex in s.exercises if ex.load.type == "external"
    ]
    assert loaded and all(ex.load.value is None for ex in loaded)


def test_real_templates_load_and_build_valid_programs():
    exercises = exercises_mod.load_exercises()
    for template in templates_mod.load_all_templates():
        program = gen_mod.build_program_from_template(
            template, exercises, equipment_profile=template.get("required_equipment", []),
            constraints=[], created="2026-08-15",
        )
        errors = model.validate_program(program)
        assert errors == [], f"{template['template_id']}: {errors}"
