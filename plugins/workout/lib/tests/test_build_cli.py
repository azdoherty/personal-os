"""End-to-end tests for the orchestration logic in program-builder's build().

The lib/ pieces are unit-tested elsewhere; this drives the real decision
path -- template match -> buildability -> generator fallback -> validate ->
save -> render -- against an in-memory database.
"""
import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

import model
import render
import store

_BUILD_PY = (
    Path(__file__).resolve().parents[2] / "skills" / "program-builder" / "scripts" / "build.py"
)


def _load_build_module():
    spec = importlib.util.spec_from_file_location("program_builder_build", _BUILD_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_mod = _load_build_module()


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    yield connection
    connection.close()


def _renders(program) -> None:
    assert render.render_markdown(program).strip()
    assert render.render_csv(program).strip()
    assert render.render_json(program).strip()


def _saved_exercise_count(connection: sqlite3.Connection, program_id: str) -> int:
    return connection.execute(
        "SELECT COUNT(*) FROM program_exercises pe JOIN sessions s USING (session_id) "
        "WHERE s.program_id = ?",
        (program_id,),
    ).fetchone()[0]


def test_curated_template_branch(conn):
    program, program_id, notes = build_mod.build(
        "beginner", 3, 40, ["dumbbell"], [], 4, conn
    )
    assert notes[0] == "Used curated template: dumbbell_beginner_3day"
    assert program.meta.source == "dumbbell_beginner_3day"
    assert model.validate_program(program) == []
    assert program.progression.block_weeks == 4 and len(program.weeks) == 4
    assert _saved_exercise_count(conn, program_id) > 0
    assert store.get_program(conn, program_id).meta.source == "dumbbell_beginner_3day"
    _renders(program)


def test_zero_equipment_user_gets_the_bodyweight_template_not_the_generator(conn):
    program, program_id, notes = build_mod.build("beginner", 3, 30, [], [], 4, conn)
    assert notes[0] == "Used curated template: bodyweight_beginner_3day"
    assert any("Dropped the pull slot" in n for n in notes)
    assert not any("No template fit" in n for n in notes)
    assert model.validate_program(program) == []
    assert all(s.exercises for w in program.weeks for s in w.sessions)
    assert _saved_exercise_count(conn, program_id) > 0
    _renders(program)


def test_requested_minutes_reach_the_saved_program_on_the_template_path(conn):
    # The dumbbell template's own session_minutes is 40; the user asked for 55.
    program, program_id, _ = build_mod.build("beginner", 3, 55, ["dumbbell"], [], 4, conn)
    assert program.meta.session_minutes == 55
    assert store.get_program(conn, program_id).meta.session_minutes == 55


def test_generator_fallback_branch_explains_itself(conn):
    # grip + arm-load rules out every dumbbell lift the curated template uses.
    program, program_id, notes = build_mod.build(
        "beginner", 3, 30, ["dumbbell", "weighted_vest"], ["grip", "arm-load"], 4, conn
    )
    assert notes[0].startswith("No template fit (")
    assert program.meta.source == "generated"
    assert model.validate_program(program) == []
    assert all(s.exercises for w in program.weeks for s in w.sessions)
    assert _saved_exercise_count(conn, program_id) > 0
    assert store.get_program(conn, program_id).meta.source == "generated"
    _renders(program)


def test_generator_fallback_flags_patterns_it_could_not_cover(conn):
    _, _, notes = build_mod.build(
        "beginner", 3, 30, ["dumbbell", "weighted_vest"], ["grip", "arm-load"], 4, conn
    )
    uncovered = next(n for n in notes if n.startswith("No eligible exercise at all for:"))
    assert "push" in uncovered and "pull" in uncovered


def test_no_buildable_program_raises_an_actionable_error_not_a_stack_trace(conn, monkeypatch):
    # Nothing in the pool is eligible for a user who owns nothing, so every
    # session would come out empty. That must be a message, not a traceback.
    monkeypatch.setattr(build_mod.exercises_mod, "load_exercises", lambda *a, **k: [
        {"exercise_id": "belt_squat", "name": "Belt Squat", "movement_pattern": "squat",
         "equipment_required": ["belt_squat_rig"], "constraint_flags": [], "ladder_group": None,
         "ladder_rank": None, "default_reps": "8-12", "notes": ""},
    ])
    with pytest.raises(build_mod.BuildError) as exc:
        build_mod.build("beginner", 3, 30, [], [], 4, conn)
    message = str(exc.value)
    assert "No eligible exercises found" in message
    assert "equipment-advisor" in message


def test_cli_rejects_a_typod_constraint_instead_of_ignoring_it(tmp_path, capsys):
    out = tmp_path / "program.md"
    code = build_mod.main([
        "--level", "beginner", "--days", "3", "--minutes", "30",
        "--constraints", "arm_load", "--out", str(out), "--db", ":memory:",
    ])
    assert code == 2
    assert "arm_load" in capsys.readouterr().err
    assert not out.exists()


def test_cli_prints_the_saved_program_id_and_creates_missing_output_dirs(tmp_path, capsys):
    out = tmp_path / "nested" / "dir" / "program.md"
    code = build_mod.main([
        "--level", "beginner", "--days", "3", "--minutes", "30",
        "--block-weeks", "2", "--out", str(out), "--db", str(tmp_path / "w.db"),
    ])
    assert code == 0
    assert "Saved as prog_" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8").startswith("# 2-Week Home Strength Program")
