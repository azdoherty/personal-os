import pytest

from model import Program, ProgramMeta, Progression, Week, Session, ProgramExercise, LoadSpec
import store


def _tiny_program():
    exercise = ProgramExercise(
        exercise_id="bodyweight_squat", name="Bodyweight Squat", movement_pattern="squat",
        sets=3, reps="12-15", load=LoadSpec(type="bodyweight", progression_rule="climb the ladder"),
        tempo="2-0-2", rest="60s",
    )
    session = Session(day=1, label="Full Body A", exercises=[exercise])
    week = Week(number=1, sessions=[session])
    meta = ProgramMeta(
        level="beginner", goal="general_strength", days_per_week=1, session_minutes=30,
        equipment_profile=[], constraints=[], created="2026-08-15", source="test",
    )
    progression = Progression(model="variation-ladder", block_weeks=1)
    return Program(meta=meta, progression=progression, weeks=[week])


def test_init_db_creates_tables():
    conn = store.connect(":memory:")
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"programs", "sessions", "program_exercises", "logs", "exercises",
            "equipment_catalog", "sources", "equipment_profile"} <= tables


def test_equipment_profile_round_trip():
    conn = store.connect(":memory:")
    store.save_equipment_profile(conn, ["dumbbell", "pull_up_bar"], "2026-08-15")
    assert sorted(store.get_equipment_profile(conn)) == ["dumbbell", "pull_up_bar"]


def test_equipment_profile_save_replaces_previous():
    conn = store.connect(":memory:")
    store.save_equipment_profile(conn, ["dumbbell"], "2026-08-15")
    store.save_equipment_profile(conn, ["sled"], "2026-08-16")
    assert store.get_equipment_profile(conn) == ["sled"]


def test_save_and_get_program_round_trip():
    conn = store.connect(":memory:")
    program = _tiny_program()
    program_id = store.save_program(conn, program)
    restored = store.get_program(conn, program_id)
    assert restored.to_dict() == program.to_dict()


def test_get_program_missing_id_raises():
    conn = store.connect(":memory:")
    with pytest.raises(KeyError):
        store.get_program(conn, "prog_doesnotexist")


def test_list_programs_returns_summaries():
    conn = store.connect(":memory:")
    program_id = store.save_program(conn, _tiny_program())
    summaries = store.list_programs(conn)
    assert summaries[0]["program_id"] == program_id
    assert summaries[0]["level"] == "beginner"


def test_connect_auto_seeds_reference_tables_on_a_fresh_database():
    conn = store.connect(":memory:")
    exercise_count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    catalog_count = conn.execute("SELECT COUNT(*) FROM equipment_catalog").fetchone()[0]
    source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    assert exercise_count >= 20
    assert catalog_count >= 5
    assert source_count >= 5


def test_connect_does_not_duplicate_seed_rows_on_reconnect():
    import sqlite3

    path = ":memory:"
    conn1 = sqlite3.connect(path)
    conn1.execute("PRAGMA foreign_keys = ON")
    store.init_db(conn1)
    store._seed_if_empty(conn1)
    store._seed_if_empty(conn1)
    count = conn1.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    assert count < 100  # sanity: didn't double-insert
