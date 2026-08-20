"""CLI-level tests for equipment-intake: token validation and --reseed."""
import importlib.util
import sys
from pathlib import Path

import pytest

import store

_INTAKE_PY = (
    Path(__file__).resolve().parents[2] / "skills" / "equipment-intake" / "scripts" / "intake.py"
)


def _load_intake_module():
    spec = importlib.util.spec_from_file_location("equipment_intake_intake", _INTAKE_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


intake_mod = _load_intake_module()


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "workout.db")


def test_set_rejects_an_unknown_equipment_id_and_saves_nothing(db_path, capsys):
    assert intake_mod.main(["--set", "dumbbell,kettlebell", "--db", db_path]) == 2
    assert "kettlebell" in capsys.readouterr().err
    conn = store.connect(db_path)
    assert store.get_equipment_profile(conn) == []
    conn.close()


def test_set_saves_a_valid_profile(db_path):
    assert intake_mod.main(["--set", "dumbbell,sled", "--db", db_path]) == 0
    conn = store.connect(db_path)
    assert sorted(store.get_equipment_profile(conn)) == ["dumbbell", "sled"]
    conn.close()


def test_reseed_restores_reference_data_the_empty_check_would_never_notice(db_path):
    conn = store.connect(db_path)
    original = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    assert original > 0

    # Mutate + partially delete: rows still exist, so _seed_if_empty stays quiet.
    conn.execute("UPDATE exercises SET name = 'STALE'")
    conn.execute("DELETE FROM exercises WHERE exercise_id = 'bodyweight_squat'")
    conn.commit()
    conn.close()

    reopened = store.connect(db_path)
    assert reopened.execute(
        "SELECT COUNT(*) FROM exercises WHERE name = 'STALE'"
    ).fetchone()[0] > 0
    reopened.close()

    assert intake_mod.main(["--reseed", "--db", db_path]) == 0

    conn = store.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0] == original
    assert conn.execute("SELECT COUNT(*) FROM exercises WHERE name = 'STALE'").fetchone()[0] == 0
    assert conn.execute(
        "SELECT name FROM exercises WHERE exercise_id = 'bodyweight_squat'"
    ).fetchone()[0] == "Bodyweight Squat"
    conn.close()


def test_reseed_leaves_the_saved_equipment_profile_alone(db_path):
    assert intake_mod.main(["--set", "dumbbell", "--db", db_path]) == 0
    assert intake_mod.main(["--reseed", "--db", db_path]) == 0
    conn = store.connect(db_path)
    assert store.get_equipment_profile(conn) == ["dumbbell"]
    conn.close()
