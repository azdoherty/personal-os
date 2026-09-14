import sqlite3

import pytest

from model import Program, ProgramMeta, Progression, Week, Session, ProgramExercise, LoadSpec
import store


# The `exercises` table exactly as it shipped before focus mode added
# `sub_category` -- i.e. what a user's existing workout.db still holds after
# they update the plugin. Kept as a literal, not derived from store.SCHEMA, so
# it stays a fixed historical record.
PRE_FOCUS_EXERCISES_SCHEMA = """
CREATE TABLE exercises (
    exercise_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    movement_pattern TEXT NOT NULL,
    equipment_required TEXT NOT NULL,
    constraint_flags TEXT NOT NULL,
    ladder_group TEXT,
    ladder_rank INTEGER,
    default_reps TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
)
"""


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


def test_init_db_adds_sub_category_to_a_pre_focus_mode_database():
    # CREATE TABLE IF NOT EXISTS is a no-op against an existing table, so
    # without a migration this database would never gain the column.
    conn = sqlite3.connect(":memory:")
    conn.execute(PRE_FOCUS_EXERCISES_SCHEMA)
    assert "sub_category" not in {
        r[1] for r in conn.execute("PRAGMA table_info(exercises)").fetchall()
    }

    store.init_db(conn)

    assert "sub_category" in {
        r[1] for r in conn.execute("PRAGMA table_info(exercises)").fetchall()
    }
    # and it is actually usable, not just listed
    assert conn.execute("SELECT sub_category FROM exercises").fetchall() == []


def test_reseeding_a_pre_focus_mode_database_succeeds_and_populates_sub_category():
    # The reported failure: `intake.py --reseed` against a store created by an
    # earlier plugin version died with
    # "OperationalError: table exercises has no column named sub_category".
    import seed

    conn = sqlite3.connect(":memory:")
    conn.execute(PRE_FOCUS_EXERCISES_SCHEMA)
    store.init_db(conn)

    counts = seed.seed_all(conn)

    assert counts["exercises"] >= 20
    tagged = conn.execute(
        "SELECT exercise_id, sub_category FROM exercises WHERE sub_category IS NOT NULL "
        "ORDER BY exercise_id"
    ).fetchall()
    assert len(tagged) >= 10
    assert ("diamond_pushup", "triceps") in tagged


def test_sub_category_migration_is_a_no_op_on_a_fresh_database():
    conn = store.connect(":memory:")
    store.init_db(conn)  # re-running must not raise "duplicate column name"
    assert "sub_category" in {
        r[1] for r in conn.execute("PRAGMA table_info(exercises)").fetchall()
    }


def test_connect_does_not_reseed_an_already_seeded_database():
    from unittest.mock import patch

    conn = store.connect(":memory:")  # auto-seeds once via connect()
    with patch("seed.seed_all") as mock_seed_all:
        store._seed_if_empty(conn)
        mock_seed_all.assert_not_called()
