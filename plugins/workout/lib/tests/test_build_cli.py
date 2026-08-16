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


@pytest.mark.parametrize("owned", [
    ["barbell", "rack"],
    ["bench", "sled"],
    ["sled", "weighted_vest"],
    ["dumbbell"],
    ["dumbbell", "bench"],
])
def test_a_user_who_owns_equipment_gets_a_program_that_actually_uses_it(conn, owned):
    # The invariant that matters to the person holding the printout: gear they
    # own shows up in the program. A curated template that ignores all of it
    # (the bodyweight block for a barbell owner) is not an acceptable answer,
    # however legitimate it looks.
    program, _, _ = build_mod.build("beginner", 3, 40, owned, [], 4, conn)
    db = {e["exercise_id"]: e for e in build_mod.exercises_mod.load_exercises()}
    used = {
        item
        for w in program.weeks for s in w.sessions for ex in s.exercises
        for item in db[ex.exercise_id]["equipment_required"]
    }
    assert used & set(owned), (
        f"{program.meta.source} put none of {owned} to work; used {sorted(used) or 'nothing'}"
    )


def test_a_runner_up_template_is_tried_when_the_best_one_is_unbuildable(conn):
    # A dumbbell owner with a grip constraint can't do a single lift in the
    # dumbbell template, but the bodyweight template fits them completely --
    # and beats the generator's identical-every-day fallback.
    program, _, notes = build_mod.build("beginner", 3, 30, ["dumbbell"], ["grip"], 4, conn)
    assert notes[0] == "Used curated template: bodyweight_beginner_3day"
    assert program.meta.source == "bodyweight_beginner_3day"
    assert model.validate_program(program) == []


@pytest.mark.parametrize("minutes", [20, 40, 55])
def test_the_printed_session_length_is_never_contradicted_by_the_content(conn, minutes):
    # Whatever produced the content owns the printed number: a template keeps
    # its own length (and says so when it differs from the request), and the
    # generator, which really does size sessions, keeps the requested one.
    import generator
    import templates as templates_mod

    program, _, notes = build_mod.build("beginner", 3, minutes, ["dumbbell"], [], 4, conn)
    if program.meta.source == "generated":
        assert program.meta.session_minutes == minutes
        slots = generator.slots_per_session(minutes)
        assert all(
            len(s.exercises) <= slots for w in program.weeks for s in w.sessions
        )
    else:
        template = next(
            t for t in templates_mod.load_all_templates()
            if t["template_id"] == program.meta.source
        )
        assert program.meta.session_minutes == template["session_minutes"]
        assert (program.meta.session_minutes == minutes) or any(
            "not the" in n and "you asked for" in n for n in notes
        )


def test_a_template_longer_than_the_users_time_budget_is_not_used(conn):
    # The dumbbell template is a 40-minute session. Handing it to someone with
    # 20 minutes -- relabelled or not -- is not a fit.
    program, _, notes = build_mod.build("beginner", 3, 20, ["dumbbell"], [], 4, conn)
    assert program.meta.source == "generated"
    assert "longer than the ~20 min you have" in notes[0]
    assert program.meta.session_minutes == 20


def test_template_carry_reps_are_trips_not_bare_numbers(conn):
    program, _, _ = build_mod.build("beginner", 3, 40, ["dumbbell"], [], 4, conn)
    carry = next(
        ex for w in program.weeks for s in w.sessions for ex in s.exercises
        if ex.exercise_id == "db_farmer_carry"
    )
    assert carry.reps == "2 trips"
    assert "4 trips" in carry.load.progression_rule


@pytest.mark.parametrize("flag,value", [("--minutes", "0"), ("--days", "0"), ("--days", "9")])
def test_cli_rejects_out_of_range_numbers_instead_of_raising(tmp_path, capsys, flag, value):
    argv = ["--level", "beginner", "--days", "3", "--minutes", "30",
            "--out", str(tmp_path / "p.md"), "--db", ":memory:"]
    argv[argv.index(flag) + 1] = value
    code = build_mod.main(argv)
    assert code == 2
    assert "error:" in capsys.readouterr().err
    assert not (tmp_path / "p.md").exists()


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
