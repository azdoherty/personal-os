from model import (
    LoadSpec, LogEntry, ProgramExercise, Session, Week, ProgramMeta,
    Progression, Program, validate_program,
)


def _tiny_program():
    exercise = ProgramExercise(
        exercise_id="bodyweight_squat", name="Bodyweight Squat", movement_pattern="squat",
        sets=3, reps="12-15", load=LoadSpec(type="bodyweight"), tempo="2-0-2", rest="60s",
    )
    session = Session(day=1, label="Full Body A", exercises=[exercise])
    week = Week(number=1, sessions=[session])
    meta = ProgramMeta(
        level="beginner", goal="general_strength", days_per_week=1, session_minutes=30,
        equipment_profile=[], constraints=[], created="2026-08-15", source="test",
    )
    progression = Progression(model="variation-ladder", block_weeks=1)
    return Program(meta=meta, progression=progression, weeks=[week])


def test_round_trip_to_dict_from_dict():
    program = _tiny_program()
    data = program.to_dict()
    restored = Program.from_dict(data)
    assert restored.to_dict() == data


def test_valid_program_has_no_errors():
    assert validate_program(_tiny_program()) == []


def test_invalid_level_is_caught():
    program = _tiny_program()
    program.meta.level = "expert"
    errors = validate_program(program)
    assert any("meta.level" in e for e in errors)


def test_week_count_mismatch_is_caught():
    program = _tiny_program()
    program.progression.block_weeks = 2
    errors = validate_program(program)
    assert any("expected 2 weeks" in e for e in errors)


def test_bad_movement_pattern_is_caught():
    program = _tiny_program()
    program.weeks[0].sessions[0].exercises[0].movement_pattern = "not-a-pattern"
    errors = validate_program(program)
    assert any("movement_pattern" in e for e in errors)


def test_bad_load_type_is_caught():
    program = _tiny_program()
    program.weeks[0].sessions[0].exercises[0].load.type = "not-a-load-type"
    errors = validate_program(program)
    assert any("load.type" in e for e in errors)


def test_session_day_out_of_range_is_caught():
    program = _tiny_program()
    program.weeks[0].sessions[0].day = 9
    errors = validate_program(program)
    assert any("session day" in e for e in errors)
