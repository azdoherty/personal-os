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


def test_template_is_constraint_compatible_false_when_all_rungs_conflict():
    assert gen_mod.template_is_constraint_compatible(SAMPLE_TEMPLATE, SAMPLE_EXERCISES, {"arm-load"}) is False


def test_template_is_constraint_compatible_true_when_no_conflicting_flags():
    assert gen_mod.template_is_constraint_compatible(SAMPLE_TEMPLATE, SAMPLE_EXERCISES, {"impact"}) is True


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
