"""SQLite persistence for the workout plugin. Local-first: one file, no
server, no network. See references/ for the git-versioned seed content
this module's companion seed.py loads.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path

from model import Program, ProgramMeta, Progression, Week, Session, ProgramExercise, LoadSpec, LogEntry

SCHEMA = """
CREATE TABLE IF NOT EXISTS equipment_profile (
    equipment_id TEXT PRIMARY KEY,
    acquired_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exercises (
    exercise_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    movement_pattern TEXT NOT NULL,
    sub_category TEXT,
    equipment_required TEXT NOT NULL,
    constraint_flags TEXT NOT NULL,
    ladder_group TEXT,
    ladder_rank INTEGER,
    default_reps TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS equipment_catalog (
    equipment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cost_tier TEXT NOT NULL,
    space_tier TEXT NOT NULL,
    approx_cost_usd REAL NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author_org TEXT NOT NULL,
    url TEXT NOT NULL,
    topic_tags TEXT NOT NULL,
    trust_tier TEXT NOT NULL,
    informs TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS programs (
    program_id TEXT PRIMARY KEY,
    level TEXT NOT NULL,
    goal TEXT NOT NULL,
    days_per_week INTEGER NOT NULL,
    session_minutes INTEGER NOT NULL,
    equipment_profile TEXT NOT NULL,
    constraints TEXT NOT NULL,
    created TEXT NOT NULL,
    source TEXT NOT NULL,
    progression_model TEXT NOT NULL,
    block_weeks INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL REFERENCES programs(program_id),
    week_number INTEGER NOT NULL,
    day INTEGER NOT NULL,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS program_exercises (
    program_exercise_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(session_id),
    exercise_id TEXT NOT NULL,
    name TEXT NOT NULL,
    movement_pattern TEXT NOT NULL,
    sets INTEGER NOT NULL,
    reps TEXT NOT NULL,
    load_type TEXT NOT NULL,
    load_value REAL,
    progression_rule TEXT NOT NULL,
    tempo TEXT NOT NULL,
    rest TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_exercise_id INTEGER NOT NULL REFERENCES program_exercises(program_exercise_id),
    date TEXT,
    sets_done INTEGER,
    reps_done TEXT,
    load_used REAL,
    rpe REAL,
    pain INTEGER
);
"""


def default_db_path() -> Path:
    """OS-appropriate, out-of-repo location for the local SQLite store."""
    import sys

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "personal-os-workout" / "workout.db"


def connect(db_path=None) -> sqlite3.Connection:
    """Open (creating parent dirs as needed), initialize, and seed the
    database from references/ if its reference tables are empty."""
    path = Path(db_path) if db_path else default_db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    _seed_if_empty(conn)
    return conn


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    if count == 0:
        import seed

        seed.seed_all(conn)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def save_equipment_profile(conn: sqlite3.Connection, equipment_ids: list, acquired_at: str) -> None:
    conn.execute("DELETE FROM equipment_profile")
    conn.executemany(
        "INSERT INTO equipment_profile (equipment_id, acquired_at) VALUES (?, ?)",
        [(eid, acquired_at) for eid in equipment_ids],
    )
    conn.commit()


def get_equipment_profile(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT equipment_id FROM equipment_profile").fetchall()
    return [r[0] for r in rows]


def new_program_id() -> str:
    return f"prog_{uuid.uuid4().hex[:12]}"


def save_program(conn: sqlite3.Connection, program: Program, program_id=None) -> str:
    program_id = program_id or new_program_id()
    meta, prog = program.meta, program.progression
    conn.execute(
        """INSERT INTO programs
           (program_id, level, goal, days_per_week, session_minutes, equipment_profile,
            constraints, created, source, progression_model, block_weeks)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            program_id, meta.level, meta.goal, meta.days_per_week, meta.session_minutes,
            json.dumps(meta.equipment_profile), json.dumps(meta.constraints), meta.created,
            meta.source, prog.model, prog.block_weeks,
        ),
    )
    for week in program.weeks:
        for session in week.sessions:
            cur = conn.execute(
                "INSERT INTO sessions (program_id, week_number, day, label) VALUES (?, ?, ?, ?)",
                (program_id, week.number, session.day, session.label),
            )
            session_id = cur.lastrowid
            for ex in session.exercises:
                conn.execute(
                    """INSERT INTO program_exercises
                       (session_id, exercise_id, name, movement_pattern, sets, reps,
                        load_type, load_value, progression_rule, tempo, rest, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id, ex.exercise_id, ex.name, ex.movement_pattern, ex.sets, ex.reps,
                        ex.load.type, ex.load.value, ex.load.progression_rule, ex.tempo, ex.rest,
                        ex.notes,
                    ),
                )
    conn.commit()
    return program_id


def get_program(conn: sqlite3.Connection, program_id: str) -> Program:
    prow = conn.execute(
        "SELECT level, goal, days_per_week, session_minutes, equipment_profile, constraints, "
        "created, source, progression_model, block_weeks FROM programs WHERE program_id = ?",
        (program_id,),
    ).fetchone()
    if prow is None:
        raise KeyError(f"no program with id {program_id!r}")
    (level, goal, days_per_week, session_minutes, equipment_profile_json, constraints_json,
     created, source, progression_model, block_weeks) = prow
    meta = ProgramMeta(
        level=level, goal=goal, days_per_week=days_per_week, session_minutes=session_minutes,
        equipment_profile=json.loads(equipment_profile_json), constraints=json.loads(constraints_json),
        created=created, source=source,
    )
    progression = Progression(model=progression_model, block_weeks=block_weeks)

    weeks_map = {}
    session_rows = conn.execute(
        "SELECT session_id, week_number, day, label FROM sessions WHERE program_id = ? "
        "ORDER BY week_number, day",
        (program_id,),
    ).fetchall()
    for session_id, week_number, day, label in session_rows:
        ex_rows = conn.execute(
            "SELECT exercise_id, name, movement_pattern, sets, reps, load_type, load_value, "
            "progression_rule, tempo, rest, notes FROM program_exercises "
            "WHERE session_id = ? ORDER BY program_exercise_id",
            (session_id,),
        ).fetchall()
        exercises = [
            ProgramExercise(
                exercise_id=r[0], name=r[1], movement_pattern=r[2], sets=r[3], reps=r[4],
                load=LoadSpec(type=r[5], value=r[6], progression_rule=r[7]),
                tempo=r[8], rest=r[9], notes=r[10], log=LogEntry(),
            )
            for r in ex_rows
        ]
        session = Session(day=day, label=label, exercises=exercises)
        weeks_map.setdefault(week_number, []).append(session)

    weeks = [Week(number=n, sessions=sessions) for n, sessions in sorted(weeks_map.items())]
    return Program(meta=meta, progression=progression, weeks=weeks)


def list_programs(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT program_id, level, goal, days_per_week, created FROM programs ORDER BY created DESC"
    ).fetchall()
    return [
        {"program_id": r[0], "level": r[1], "goal": r[2], "days_per_week": r[3], "created": r[4]}
        for r in rows
    ]
