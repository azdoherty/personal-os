import csv
import io
import json

import render
from model import Program, ProgramMeta, Progression, Week, Session, ProgramExercise, LoadSpec


def _program():
    ex1 = ProgramExercise(
        exercise_id="bodyweight_squat", name="Bodyweight Squat", movement_pattern="squat",
        sets=3, reps="12-15", load=LoadSpec(type="bodyweight", progression_rule="climb the ladder"),
        tempo="2-0-2", rest="60s", notes="Keep the chest tall.",
    )
    ex2 = ProgramExercise(
        exercise_id="db_goblet_squat", name="DB Goblet Squat", movement_pattern="squat",
        sets=3, reps="8", load=LoadSpec(type="external", value=15.0, progression_rule="add a rep"),
        tempo="3-0-1", rest="90s", notes="",
    )
    session = Session(day=1, label="Full Body A", exercises=[ex1, ex2])
    week = Week(number=1, sessions=[session])
    meta = ProgramMeta(
        level="beginner", goal="general_strength", days_per_week=1, session_minutes=30,
        equipment_profile=["dumbbell"], constraints=[], created="2026-08-15", source="test",
    )
    return Program(meta=meta, progression=Progression(model="double-progression", block_weeks=1), weeks=[week])


def test_render_markdown_includes_header_and_exercises():
    text = render.render_markdown(_program())
    assert "Week 1" in text
    assert "Day 1 — Full Body A" in text
    assert "Bodyweight Squat" in text
    assert "DB Goblet Squat" in text
    assert "15" in text


def test_render_markdown_carries_the_not_medical_advice_disclaimer():
    text = render.render_markdown(_program())
    assert "not medical advice" in text
    assert text.index("not medical advice") < text.index("Week 1")


def test_render_markdown_shows_fill_in_blank_for_unset_load():
    program = _program()
    program.weeks[0].sessions[0].exercises[1].load.value = None
    text = render.render_markdown(program)
    assert "start light, log it" in text


def test_render_csv_has_one_row_per_exercise_with_header():
    text = render.render_csv(_program())
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][0] == "week"
    assert len(rows) == 3
    assert rows[1][3] == "Bodyweight Squat"


def test_render_json_round_trips_through_model():
    program = _program()
    text = render.render_json(program)
    restored = Program.from_dict(json.loads(text))
    assert restored.to_dict() == program.to_dict()
