# Workout Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `plugins/workout/`, a third `personal-os` marketplace plugin that generates progressive, printable home-strength programs tailored to the user's equipment and physical constraints, and advises on equipment gaps with a handoff to the `research` plugin.

**Architecture:** Thin `SKILL.md` skills over a stdlib-only `lib/` engine (model, SQLite store, exercise/template data loaders, progression engine, generator, renderers), backed by git-versioned `references/` content seeded into a local SQLite database on init. No network calls, no cloud services — local-first, single-file storage.

**Tech Stack:** Python 3 standard library only (`dataclasses`, `sqlite3`, `json`, `csv`, `re`, `argparse`, `uuid`, `pathlib`) — no pip dependencies, matching the rest of this repo. `pytest` for tests (already used by the `rental` plugin's test suite per `CLAUDE.md`).

## Global Constraints

- Stdlib-only Python; no pip dependencies (repo-wide convention, see `CLAUDE.md`).
- No cloud infrastructure: SQLite is the sole system of record, stored outside the repo (OS config dir), backed up by the user copying one file.
- v1 ships a one-shot program (progression baked in at generation time) with a data model ready for later adaptive/phone-logging use — the `log` fields exist but are never written in v1.
- Every plugin file change must keep `.claude-plugin/marketplace.json` and `plugins/workout/.claude-plugin/plugin.json` valid JSON.
- Approved design spec: `docs/superpowers/specs/2026-08-15-workout-plugin-design.md` — this plan implements it in full; do not deviate without updating the spec first.

---

## Task 1: Plugin scaffold

**Files:**
- Create: `plugins/workout/.claude-plugin/plugin.json`
- Create: `plugins/workout/lib/__init__.py`
- Create: `plugins/workout/lib/tests/__init__.py`
- Create: `plugins/workout/lib/tests/conftest.py`
- Create: `plugins/workout/references/.gitkeep`
- Create: `plugins/workout/references/templates/.gitkeep`
- Modify: `.claude-plugin/marketplace.json`

**Interfaces:**
- Produces: `plugins/workout/lib/` is importable by any test file under `lib/tests/` via a bare `import <module>` (no per-file `sys.path` boilerplate) because `conftest.py` inserts the `lib/` directory onto `sys.path` once, automatically, for every test in the directory.

- [ ] **Step 1: Create the plugin manifest**

```json
{
  "name": "workout",
  "version": "0.1.0",
  "description": "Progressive home-strength programs tailored to your equipment and physical constraints: curated templates plus a generator/remix engine, an equipment gap advisor with research-plugin handoff, local SQLite storage, and printable markdown/CSV/artifact outputs.",
  "author": { "name": "azdoh", "email": "your-email@example.com" }
}
```

Write this to `plugins/workout/.claude-plugin/plugin.json`.

- [ ] **Step 2: Verify the manifest is valid JSON**

Run: `python -c "import json; json.load(open('plugins/workout/.claude-plugin/plugin.json'))" && echo OK`
Expected: `OK`

- [ ] **Step 3: Register the plugin in the marketplace**

Read `.claude-plugin/marketplace.json` first — it currently ends with:

```json
    {
      "name": "research",
      "description": "Literature review for purchases and questions: searches Reddit (with engagement data), HN, StackExchange, and the web; verifies brand legitimacy; scores source trust; produces a cited summary.",
      "source": "./plugins/research",
      "category": "productivity"
    }
  ]
}
```

Replace that closing with (adds a comma after the research entry and a new `workout` entry):

```json
    {
      "name": "research",
      "description": "Literature review for purchases and questions: searches Reddit (with engagement data), HN, StackExchange, and the web; verifies brand legitimacy; scores source trust; produces a cited summary.",
      "source": "./plugins/research",
      "category": "productivity"
    },
    {
      "name": "workout",
      "description": "Progressive home-strength programs from a curated template + generator engine, equipment-aware and injury-aware; equipment gap advisor with research-plugin handoff; local SQLite storage; printable markdown/CSV/artifact outputs.",
      "source": "./plugins/workout",
      "category": "productivity"
    }
  ]
}
```

- [ ] **Step 4: Verify the marketplace manifest is still valid JSON**

Run: `python -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print([p['name'] for p in d['plugins']])"`
Expected: `['research', 'workout']`

- [ ] **Step 5: Scaffold the lib package and its test harness**

Create `plugins/workout/lib/__init__.py` (empty file).

Create `plugins/workout/lib/tests/__init__.py` (empty file).

Create `plugins/workout/lib/tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 6: Scaffold the references directories**

Create `plugins/workout/references/.gitkeep` (empty file) and `plugins/workout/references/templates/.gitkeep` (empty file) so the directories exist in git before their content lands in later tasks.

- [ ] **Step 7: Commit**

```bash
git add plugins/workout/.claude-plugin/plugin.json plugins/workout/lib/__init__.py \
    plugins/workout/lib/tests/__init__.py plugins/workout/lib/tests/conftest.py \
    plugins/workout/references/.gitkeep plugins/workout/references/templates/.gitkeep \
    .claude-plugin/marketplace.json
git commit -m "feat(workout): scaffold plugin and register in marketplace"
```

---

## Task 2: Program data model

**Files:**
- Create: `plugins/workout/lib/model.py`
- Test: `plugins/workout/lib/tests/test_model.py`

**Interfaces:**
- Consumes: nothing (foundation module).
- Produces: `MOVEMENT_PATTERNS`, `CONSTRAINT_FLAGS`, `PROGRESSION_MODELS`, `LOAD_TYPES`, `LEVELS` tuples; `LoadSpec`, `LogEntry`, `ProgramExercise`, `Session`, `Week`, `ProgramMeta`, `Progression`, `Program` dataclasses, each with `.to_dict()` and a `.from_dict(data)` classmethod; `validate_program(program: Program) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/workout/lib/tests/test_model.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'model'`

- [ ] **Step 3: Implement the model**

Create `plugins/workout/lib/model.py`:

```python
"""Program data model: the schema shared by curated templates, the
generator, SQLite storage, and every renderer.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

MOVEMENT_PATTERNS = ("squat", "hinge", "push", "pull", "carry", "core")
CONSTRAINT_FLAGS = ("grip", "arm-load", "overhead", "spinal-load", "impact")
PROGRESSION_MODELS = ("double-progression", "linear", "variation-ladder")
LOAD_TYPES = ("bodyweight", "external", "band")
LEVELS = ("beginner", "intermediate")


@dataclass
class LoadSpec:
    type: str
    value: Optional[float] = None
    progression_rule: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "value": self.value, "progression_rule": self.progression_rule}

    @classmethod
    def from_dict(cls, data: dict) -> "LoadSpec":
        return cls(type=data["type"], value=data.get("value"), progression_rule=data.get("progression_rule", ""))


@dataclass
class LogEntry:
    date: Optional[str] = None
    sets_done: Optional[int] = None
    reps_done: Optional[list] = None
    load_used: Optional[float] = None
    rpe: Optional[float] = None
    pain: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "date": self.date, "sets_done": self.sets_done, "reps_done": self.reps_done,
            "load_used": self.load_used, "rpe": self.rpe, "pain": self.pain,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LogEntry":
        return cls(
            date=data.get("date"), sets_done=data.get("sets_done"), reps_done=data.get("reps_done"),
            load_used=data.get("load_used"), rpe=data.get("rpe"), pain=data.get("pain"),
        )


@dataclass
class ProgramExercise:
    exercise_id: str
    name: str
    movement_pattern: str
    sets: int
    reps: str
    load: LoadSpec
    tempo: str
    rest: str
    notes: str = ""
    log: LogEntry = field(default_factory=LogEntry)

    def to_dict(self) -> dict:
        return {
            "exercise_id": self.exercise_id, "name": self.name,
            "movement_pattern": self.movement_pattern, "sets": self.sets, "reps": self.reps,
            "load": self.load.to_dict(), "tempo": self.tempo, "rest": self.rest,
            "notes": self.notes, "log": self.log.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProgramExercise":
        return cls(
            exercise_id=data["exercise_id"], name=data["name"],
            movement_pattern=data["movement_pattern"], sets=data["sets"], reps=data["reps"],
            load=LoadSpec.from_dict(data["load"]), tempo=data["tempo"], rest=data["rest"],
            notes=data.get("notes", ""), log=LogEntry.from_dict(data.get("log", {})),
        )


@dataclass
class Session:
    day: int
    label: str
    exercises: list

    def to_dict(self) -> dict:
        return {"day": self.day, "label": self.label, "exercises": [e.to_dict() for e in self.exercises]}

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(day=data["day"], label=data["label"],
                    exercises=[ProgramExercise.from_dict(e) for e in data["exercises"]])


@dataclass
class Week:
    number: int
    sessions: list

    def to_dict(self) -> dict:
        return {"number": self.number, "sessions": [s.to_dict() for s in self.sessions]}

    @classmethod
    def from_dict(cls, data: dict) -> "Week":
        return cls(number=data["number"], sessions=[Session.from_dict(s) for s in data["sessions"]])


@dataclass
class ProgramMeta:
    level: str
    goal: str
    days_per_week: int
    session_minutes: int
    equipment_profile: list
    constraints: list
    created: str
    source: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProgramMeta":
        return cls(**data)


@dataclass
class Progression:
    model: str
    block_weeks: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Progression":
        return cls(**data)


@dataclass
class Program:
    meta: ProgramMeta
    progression: Progression
    weeks: list

    def to_dict(self) -> dict:
        return {
            "meta": self.meta.to_dict(),
            "progression": self.progression.to_dict(),
            "weeks": [w.to_dict() for w in self.weeks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Program":
        return cls(
            meta=ProgramMeta.from_dict(data["meta"]),
            progression=Progression.from_dict(data["progression"]),
            weeks=[Week.from_dict(w) for w in data["weeks"]],
        )


def validate_program(program: Program) -> list:
    """Return a list of human-readable validation errors. Empty list = valid."""
    errors = []
    meta = program.meta
    if meta.level not in LEVELS:
        errors.append(f"meta.level must be one of {LEVELS}, got {meta.level!r}")
    if not (1 <= meta.days_per_week <= 7):
        errors.append(f"meta.days_per_week must be 1-7, got {meta.days_per_week}")
    if meta.session_minutes <= 0:
        errors.append(f"meta.session_minutes must be positive, got {meta.session_minutes}")

    prog = program.progression
    if prog.model not in PROGRESSION_MODELS:
        errors.append(f"progression.model must be one of {PROGRESSION_MODELS}, got {prog.model!r}")
    if prog.block_weeks <= 0:
        errors.append(f"progression.block_weeks must be positive, got {prog.block_weeks}")

    if len(program.weeks) != prog.block_weeks:
        errors.append(
            f"expected {prog.block_weeks} weeks (progression.block_weeks), got {len(program.weeks)}"
        )

    for i, week in enumerate(program.weeks, start=1):
        if week.number != i:
            errors.append(f"weeks[{i - 1}].number expected {i}, got {week.number}")
        for session in week.sessions:
            if not (1 <= session.day <= meta.days_per_week):
                errors.append(
                    f"week {week.number} session day {session.day} outside 1..{meta.days_per_week}"
                )
            for ex in session.exercises:
                if ex.movement_pattern not in MOVEMENT_PATTERNS:
                    errors.append(
                        f"week {week.number} exercise {ex.exercise_id!r} has invalid "
                        f"movement_pattern {ex.movement_pattern!r}"
                    )
                if ex.load.type not in LOAD_TYPES:
                    errors.append(
                        f"week {week.number} exercise {ex.exercise_id!r} has invalid "
                        f"load.type {ex.load.type!r}"
                    )
                if ex.sets <= 0:
                    errors.append(
                        f"week {week.number} exercise {ex.exercise_id!r} has non-positive sets"
                    )
    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_model.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/workout/lib/model.py plugins/workout/lib/tests/test_model.py
git commit -m "feat(workout): add Program data model and validation"
```

---

## Task 3: SQLite storage

**Files:**
- Create: `plugins/workout/lib/store.py`
- Test: `plugins/workout/lib/tests/test_store.py`

**Interfaces:**
- Consumes: `model.Program`, `model.ProgramMeta`, `model.Progression`, `model.Week`, `model.Session`, `model.ProgramExercise`, `model.LoadSpec`, `model.LogEntry` (Task 2).
- Produces: `default_db_path() -> Path`, `connect(db_path=None) -> sqlite3.Connection`, `init_db(conn)`, `save_equipment_profile(conn, equipment_ids, acquired_at)`, `get_equipment_profile(conn) -> list[str]`, `new_program_id() -> str`, `save_program(conn, program, program_id=None) -> str`, `get_program(conn, program_id) -> Program`, `list_programs(conn) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/workout/lib/tests/test_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'store'`

- [ ] **Step 3: Implement the store**

Create `plugins/workout/lib/store.py`:

```python
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
    """Open (creating parent dirs as needed) and initialize the database."""
    path = Path(db_path) if db_path else default_db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_store.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/workout/lib/store.py plugins/workout/lib/tests/test_store.py
git commit -m "feat(workout): add SQLite storage layer"
```

---

## Task 4: Exercise database

**Files:**
- Create: `plugins/workout/references/exercises.json`
- Create: `plugins/workout/lib/exercises.py`
- Test: `plugins/workout/lib/tests/test_exercises.py`

**Interfaces:**
- Consumes: nothing beyond the JSON file it loads.
- Produces: `load_exercises(path=None) -> list[dict]`, `is_eligible(exercise, equipment_ids, excluded_constraints) -> bool`, `filter_exercises(exercises, equipment_ids, excluded_constraints) -> list[dict]`, `group_by_pattern(exercises) -> dict[str, list[dict]]`, `ladder_for_group(exercises, ladder_group) -> list[dict]`, `find_by_id(exercises, exercise_id) -> dict`. Each exercise dict has keys: `exercise_id, name, movement_pattern, equipment_required, constraint_flags, ladder_group, ladder_rank, default_reps, notes`.

- [ ] **Step 1: Write the exercise database**

Create `plugins/workout/references/exercises.json`:

```json
[
  {"exercise_id": "box_squat", "name": "Box Squat", "movement_pattern": "squat", "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw", "ladder_rank": 0, "default_reps": "10-15", "notes": "Sit back onto a chair or box, stand back up. Lightly touch and go."},
  {"exercise_id": "bodyweight_squat", "name": "Bodyweight Squat", "movement_pattern": "squat", "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw", "ladder_rank": 1, "default_reps": "12-15", "notes": "Feet shoulder-width, sit the hips back and down, chest tall."},
  {"exercise_id": "bulgarian_split_squat_bw", "name": "Bulgarian Split Squat (bodyweight)", "movement_pattern": "squat", "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw", "ladder_rank": 2, "default_reps": "8-10 / leg", "notes": "Rear foot elevated on a chair; lower the back knee toward the floor."},

  {"exercise_id": "glute_bridge", "name": "Glute Bridge", "movement_pattern": "hinge", "equipment_required": [], "constraint_flags": [], "ladder_group": "hinge_bw", "ladder_rank": 0, "default_reps": "12-15", "notes": "Lie on your back, drive the hips up, squeeze the glutes at the top."},
  {"exercise_id": "single_leg_glute_bridge", "name": "Single-Leg Glute Bridge", "movement_pattern": "hinge", "equipment_required": [], "constraint_flags": [], "ladder_group": "hinge_bw", "ladder_rank": 1, "default_reps": "10-12 / leg", "notes": "Same as glute bridge with one foot lifted."},
  {"exercise_id": "single_leg_rdl_bw", "name": "Single-Leg RDL (bodyweight)", "movement_pattern": "hinge", "equipment_required": [], "constraint_flags": [], "ladder_group": "hinge_bw", "ladder_rank": 2, "default_reps": "8-10 / leg", "notes": "Hinge at the hips on one leg, arms free for balance; keep the back flat."},

  {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "movement_pattern": "push", "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push_bw", "ladder_rank": 0, "default_reps": "8-12", "notes": "Hands on a sturdy elevated surface, body in a straight line."},
  {"exercise_id": "pushup", "name": "Push-Up", "movement_pattern": "push", "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push_bw", "ladder_rank": 1, "default_reps": "10-15", "notes": "Hands on the floor, body in a straight line, elbows ~45 degrees from the torso."},
  {"exercise_id": "decline_pushup", "name": "Decline Push-Up", "movement_pattern": "push", "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push_bw", "ladder_rank": 2, "default_reps": "8-12", "notes": "Feet elevated on a chair or step."},

  {"exercise_id": "table_inverted_row_bent", "name": "Table Inverted Row (bent knees)", "movement_pattern": "pull", "equipment_required": ["sturdy_table"], "constraint_flags": ["arm-load", "grip"], "ladder_group": "pull_bw", "ladder_rank": 0, "default_reps": "8-12", "notes": "Lie under a sturdy table, knees bent, pull the chest to the table edge."},
  {"exercise_id": "table_inverted_row", "name": "Table Inverted Row", "movement_pattern": "pull", "equipment_required": ["sturdy_table"], "constraint_flags": ["arm-load", "grip"], "ladder_group": "pull_bw", "ladder_rank": 1, "default_reps": "8-10", "notes": "Same as the bent-knee version with legs straight."},

  {"exercise_id": "dead_bug", "name": "Dead Bug", "movement_pattern": "core", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_bw", "ladder_rank": 0, "default_reps": "10-12 / side", "notes": "Lower the opposite arm and leg slowly, keep the low back pressed to the floor."},
  {"exercise_id": "plank", "name": "Plank", "movement_pattern": "core", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_bw", "ladder_rank": 1, "default_reps": "30-45s", "notes": "Forearms and toes on the floor, body in a straight line."},
  {"exercise_id": "side_plank", "name": "Side Plank", "movement_pattern": "core", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_bw", "ladder_rank": 2, "default_reps": "20-30s / side", "notes": "Stack the feet, prop up on one forearm, hips lifted."},

  {"exercise_id": "db_goblet_squat", "name": "DB Goblet Squat", "movement_pattern": "squat", "equipment_required": ["dumbbell"], "constraint_flags": ["grip"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Hold one dumbbell vertically at the chest, squat between the knees."},
  {"exercise_id": "db_romanian_deadlift", "name": "DB Romanian Deadlift", "movement_pattern": "hinge", "equipment_required": ["dumbbell"], "constraint_flags": ["grip"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Hinge at the hips, dumbbells stay close to the legs, slight knee bend."},
  {"exercise_id": "db_bench_press_floor", "name": "DB Floor Press", "movement_pattern": "push", "equipment_required": ["dumbbell"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Lie on the floor, press dumbbells straight up over the shoulders."},
  {"exercise_id": "db_bench_press", "name": "DB Bench Press", "movement_pattern": "push", "equipment_required": ["dumbbell", "bench"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Same as the floor press with a full range of motion on a bench."},
  {"exercise_id": "db_bent_over_row", "name": "DB Bent-Over Row", "movement_pattern": "pull", "equipment_required": ["dumbbell"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Hinge forward ~45 degrees, pull the elbows past the ribs."},
  {"exercise_id": "db_farmer_carry", "name": "DB Farmer's Carry", "movement_pattern": "carry", "equipment_required": ["dumbbell"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "2-4 trips", "notes": "Trips of ~30m each, walk tall with shoulders back."},
  {"exercise_id": "pullup_band_assisted", "name": "Band-Assisted Pull-Up", "movement_pattern": "pull", "equipment_required": ["pull_up_bar", "resistance_band"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "4-8", "notes": "Loop a band over the bar and under a knee or foot for assistance."},

  {"exercise_id": "weighted_vest_split_squat", "name": "Weighted Vest Split Squat", "movement_pattern": "squat", "equipment_required": ["weighted_vest"], "constraint_flags": [], "ladder_group": null, "ladder_rank": null, "default_reps": "8-10 / leg", "notes": "Wear the vest, hands free at your sides for balance only -- no grip or arm load."},
  {"exercise_id": "sled_push", "name": "Sled Push (hip harness)", "movement_pattern": "squat", "equipment_required": ["sled"], "constraint_flags": [], "ladder_group": null, "ladder_rank": null, "default_reps": "3-5 trips", "notes": "Pull from a hip harness, hands empty at your sides -- no grip or arm load."},
  {"exercise_id": "belt_squat", "name": "Belt Squat", "movement_pattern": "squat", "equipment_required": ["belt_squat_rig"], "constraint_flags": [], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Load hangs from a belt around the hips -- no grip or arm load."},

  {"exercise_id": "barbell_back_squat", "name": "Barbell Back Squat", "movement_pattern": "squat", "equipment_required": ["barbell", "rack"], "constraint_flags": ["grip", "spinal-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "5-8", "notes": "Bar racked across the upper back, squat to depth."},
  {"exercise_id": "barbell_romanian_deadlift", "name": "Barbell Romanian Deadlift", "movement_pattern": "hinge", "equipment_required": ["barbell"], "constraint_flags": ["grip", "spinal-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "6-10", "notes": "Hinge at the hips holding the bar, bar stays close to the legs."}
]
```

- [ ] **Step 2: Write the failing tests**

Create `plugins/workout/lib/tests/test_exercises.py`:

```python
import pytest

import exercises as ex_mod


SAMPLE = [
    {"exercise_id": "a", "name": "A", "movement_pattern": "squat",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "sq", "ladder_rank": 0,
     "default_reps": "10-15", "notes": ""},
    {"exercise_id": "b", "name": "B", "movement_pattern": "squat",
     "equipment_required": ["dumbbell"], "constraint_flags": ["grip"], "ladder_group": None,
     "ladder_rank": None, "default_reps": "8-12", "notes": ""},
    {"exercise_id": "c", "name": "C", "movement_pattern": "push",
     "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push",
     "ladder_rank": 0, "default_reps": "8-12", "notes": ""},
]


def test_filter_excludes_missing_equipment():
    result = ex_mod.filter_exercises(SAMPLE, equipment_ids=[], excluded_constraints=[])
    ids = {e["exercise_id"] for e in result}
    assert ids == {"a", "c"}


def test_filter_excludes_constraint_flagged_exercises():
    result = ex_mod.filter_exercises(SAMPLE, equipment_ids=["dumbbell"], excluded_constraints=["arm-load"])
    ids = {e["exercise_id"] for e in result}
    assert ids == {"a", "b"}


def test_filter_arm_free_leaves_only_arm_free_options():
    result = ex_mod.filter_exercises(
        SAMPLE, equipment_ids=["dumbbell"], excluded_constraints=["grip", "arm-load"]
    )
    ids = {e["exercise_id"] for e in result}
    assert ids == {"a"}


def test_group_by_pattern():
    grouped = ex_mod.group_by_pattern(SAMPLE)
    assert len(grouped["squat"]) == 2
    assert len(grouped["push"]) == 1


def test_ladder_for_group_orders_by_rank():
    exercises = SAMPLE + [
        {"exercise_id": "a2", "name": "A2", "movement_pattern": "squat", "equipment_required": [],
         "constraint_flags": [], "ladder_group": "sq", "ladder_rank": 1, "default_reps": "8-10",
         "notes": ""},
    ]
    ladder = ex_mod.ladder_for_group(exercises, "sq")
    assert [e["exercise_id"] for e in ladder] == ["a", "a2"]


def test_find_by_id_raises_for_unknown():
    with pytest.raises(KeyError):
        ex_mod.find_by_id(SAMPLE, "nonexistent")


def test_real_exercise_db_loads_and_has_expected_shape():
    real = ex_mod.load_exercises()
    assert len(real) >= 20
    ids = {e["exercise_id"] for e in real}
    assert "bodyweight_squat" in ids
    assert "weighted_vest_split_squat" in ids
    for e in real:
        assert e["movement_pattern"] in {"squat", "hinge", "push", "pull", "carry", "core"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_exercises.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exercises'`

- [ ] **Step 4: Implement the exercise loader**

Create `plugins/workout/lib/exercises.py`:

```python
"""Exercise database loading and equipment/constraint-aware filtering."""
from __future__ import annotations

import json
from pathlib import Path

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"


def load_exercises(path=None) -> list:
    """Load the exercise DB from references/exercises.json (or an override path)."""
    path = path or (REFERENCES_DIR / "exercises.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_eligible(exercise: dict, equipment_ids: set, excluded_constraints: set) -> bool:
    """An exercise is eligible if every piece of required equipment is owned
    and none of its constraint flags are in the excluded set."""
    required = set(exercise.get("equipment_required", []))
    if not required.issubset(equipment_ids):
        return False
    flags = set(exercise.get("constraint_flags", []))
    if flags & excluded_constraints:
        return False
    return True


def filter_exercises(exercises: list, equipment_ids, excluded_constraints) -> list:
    equipment_ids = set(equipment_ids)
    excluded_constraints = set(excluded_constraints)
    return [e for e in exercises if is_eligible(e, equipment_ids, excluded_constraints)]


def group_by_pattern(exercises: list) -> dict:
    grouped: dict = {}
    for e in exercises:
        grouped.setdefault(e["movement_pattern"], []).append(e)
    return grouped


def ladder_for_group(exercises: list, ladder_group: str) -> list:
    """Return the exercises in a ladder group, ordered easiest -> hardest."""
    rungs = [e for e in exercises if e.get("ladder_group") == ladder_group]
    return sorted(rungs, key=lambda e: e["ladder_rank"])


def find_by_id(exercises: list, exercise_id: str) -> dict:
    for e in exercises:
        if e["exercise_id"] == exercise_id:
            return e
    raise KeyError(f"no exercise with id {exercise_id!r}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_exercises.py -v`
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add plugins/workout/references/exercises.json plugins/workout/lib/exercises.py \
    plugins/workout/lib/tests/test_exercises.py
git commit -m "feat(workout): add exercise database and equipment/constraint filtering"
```

---

## Task 5: Equipment catalog data

**Files:**
- Create: `plugins/workout/references/equipment.json`

**Interfaces:**
- Produces: JSON array of equipment catalog entries, each with keys `equipment_id, name, cost_tier, space_tier, approx_cost_usd, notes`. Consumed by `lib/advisor.py` (Task 11) and seeded into SQLite by `lib/seed.py` (Task 10).

- [ ] **Step 1: Write the equipment catalog**

Create `plugins/workout/references/equipment.json`:

```json
[
  {"equipment_id": "dumbbell", "name": "Adjustable Dumbbells (pair)", "cost_tier": "medium", "space_tier": "small", "approx_cost_usd": 250, "notes": "The single highest-value first purchase; unlocks squat, hinge, push, pull, and carry patterns."},
  {"equipment_id": "resistance_band", "name": "Resistance Band Set", "cost_tier": "low", "space_tier": "small", "approx_cost_usd": 30, "notes": "Cheap assistance for pull-up progressions."},
  {"equipment_id": "pull_up_bar", "name": "Doorway Pull-Up Bar", "cost_tier": "low", "space_tier": "small", "approx_cost_usd": 30, "notes": "Needed alongside a resistance band for assisted pull-ups."},
  {"equipment_id": "weighted_vest", "name": "Weighted Vest (20-40 lb)", "cost_tier": "medium", "space_tier": "small", "approx_cost_usd": 100, "notes": "Loads squat-pattern work with zero grip or arm involvement -- useful when avoiding grip/arm-load."},
  {"equipment_id": "sled", "name": "Drag Sled / Loaded Tire Rig", "cost_tier": "low", "space_tier": "medium", "approx_cost_usd": 40, "notes": "Heavy leg work pulled from a hip harness -- arm-free."},
  {"equipment_id": "belt_squat_rig", "name": "Belt Squat Machine", "cost_tier": "high", "space_tier": "large", "approx_cost_usd": 800, "notes": "Heaviest arm-free squat option; a big-ticket item."},
  {"equipment_id": "barbell", "name": "Barbell + Plates", "cost_tier": "medium", "space_tier": "medium", "approx_cost_usd": 300, "notes": "Enables the heaviest loaded squat/hinge work; grip- and spine-loading."},
  {"equipment_id": "rack", "name": "Squat Rack", "cost_tier": "high", "space_tier": "large", "approx_cost_usd": 400, "notes": "Needed to safely rack/unrack a loaded barbell squat."},
  {"equipment_id": "sturdy_table", "name": "Sturdy Table (for inverted rows)", "cost_tier": "none", "space_tier": "none", "approx_cost_usd": 0, "notes": "Most households already have one; the free way to train the pull pattern with no other equipment."},
  {"equipment_id": "bench", "name": "Adjustable Bench", "cost_tier": "medium", "space_tier": "medium", "approx_cost_usd": 150, "notes": "Upgrades floor pressing to a full-range bench press."}
]
```

- [ ] **Step 2: Verify it's valid JSON with the ids the exercise DB expects**

Run:
```bash
python -c "
import json
items = json.load(open('plugins/workout/references/equipment.json'))
exercises = json.load(open('plugins/workout/references/exercises.json'))
catalog_ids = {i['equipment_id'] for i in items}
used_ids = {eid for e in exercises for eid in e['equipment_required']}
missing = used_ids - catalog_ids
print('catalog size:', len(items))
print('missing from catalog:', missing)
assert not missing
print('OK')
"
```
Expected: `catalog size: 10`, `missing from catalog: set()`, `OK`

- [ ] **Step 3: Commit**

```bash
git add plugins/workout/references/equipment.json
git commit -m "feat(workout): add equipment catalog reference data"
```

---

## Task 6: Progression engine

**Files:**
- Create: `plugins/workout/lib/progression.py`
- Test: `plugins/workout/lib/tests/test_progression.py`

**Interfaces:**
- Consumes: `model.PROGRESSION_MODELS` (Task 2).
- Produces: `apply_linear(exercise_cfg, week_number) -> dict`, `apply_double_progression(exercise_cfg, week_number) -> dict`, `apply_variation_ladder(exercise_cfg, week_number, ladder) -> dict`, `generate_block(exercise_cfg, block_weeks, model, ladder=None) -> list[dict]`. Each per-week dict from the loaded models has keys `sets, reps, load_type, load_value`; the variation-ladder dict has keys `exercise_id, name, sets, reps, load_type, load_value`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/workout/lib/tests/test_progression.py`:

```python
import pytest

import progression as prog_mod


def test_apply_linear_holds_for_first_week():
    cfg = {"sets": 3, "reps": "5", "load_value": 20.0, "increment": 5.0, "increment_every_weeks": 2}
    week1 = prog_mod.apply_linear(cfg, 1)
    assert week1["load_value"] == 20.0


def test_apply_linear_increments_on_schedule():
    cfg = {"sets": 3, "reps": "5", "load_value": 20.0, "increment": 5.0, "increment_every_weeks": 2}
    assert prog_mod.apply_linear(cfg, 3)["load_value"] == 25.0
    assert prog_mod.apply_linear(cfg, 5)["load_value"] == 30.0


def test_double_progression_climbs_reps_then_resets_with_load_bump():
    cfg = {
        "sets": 3, "reps_low": 8, "reps_high": 10, "rep_step": 1,
        "load_value": 15.0, "load_increment": 5.0,
    }
    week1 = prog_mod.apply_double_progression(cfg, 1)
    week3 = prog_mod.apply_double_progression(cfg, 3)
    week4 = prog_mod.apply_double_progression(cfg, 4)
    assert week1["reps"] == "8" and week1["load_value"] == 15.0
    assert week3["reps"] == "10" and week3["load_value"] == 15.0
    assert week4["reps"] == "8" and week4["load_value"] == 20.0


def test_double_progression_handles_unset_load():
    cfg = {"sets": 3, "reps_low": 8, "reps_high": 9, "rep_step": 1, "load_value": None, "load_increment": 5.0}
    week1 = prog_mod.apply_double_progression(cfg, 1)
    week3 = prog_mod.apply_double_progression(cfg, 3)
    assert week1["load_value"] is None
    assert week3["load_value"] is None


def test_variation_ladder_climbs_one_rung_per_interval():
    ladder = [
        {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "default_reps": "8-12"},
        {"exercise_id": "pushup", "name": "Push-Up", "default_reps": "10-15"},
        {"exercise_id": "decline_pushup", "name": "Decline Push-Up", "default_reps": "8-12"},
    ]
    cfg = {"sets": 3, "weeks_per_rung": 2}
    assert prog_mod.apply_variation_ladder(cfg, 1, ladder)["exercise_id"] == "incline_pushup"
    assert prog_mod.apply_variation_ladder(cfg, 3, ladder)["exercise_id"] == "pushup"
    assert prog_mod.apply_variation_ladder(cfg, 5, ladder)["exercise_id"] == "decline_pushup"


def test_variation_ladder_caps_at_top_rung():
    ladder = [
        {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "default_reps": "8-12"},
        {"exercise_id": "pushup", "name": "Push-Up", "default_reps": "10-15"},
    ]
    cfg = {"sets": 3, "weeks_per_rung": 2}
    assert prog_mod.apply_variation_ladder(cfg, 100, ladder)["exercise_id"] == "pushup"


def test_generate_block_dispatches_by_model():
    cfg = {"sets": 3, "reps_low": 8, "reps_high": 9, "rep_step": 1, "load_value": 10.0, "load_increment": 5.0}
    weeks = prog_mod.generate_block(cfg, block_weeks=4, model="double-progression")
    assert len(weeks) == 4


def test_generate_block_variation_ladder_requires_ladder():
    cfg = {"sets": 3, "weeks_per_rung": 2}
    with pytest.raises(ValueError):
        prog_mod.generate_block(cfg, block_weeks=4, model="variation-ladder")


def test_generate_block_unknown_model_raises():
    with pytest.raises(ValueError):
        prog_mod.generate_block({}, block_weeks=1, model="not-a-model")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_progression.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'progression'`

- [ ] **Step 3: Implement the progression engine**

Create `plugins/workout/lib/progression.py`:

```python
"""Deterministic progression: given an exercise's starting configuration and
a block length, compute the sets/reps/load for every week of the block up
front (v1 is one-shot -- see model.py's log fields for the future adaptive
hook). Three models, matching model.PROGRESSION_MODELS.
"""
from __future__ import annotations

from model import PROGRESSION_MODELS


def apply_linear(exercise_cfg: dict, week_number: int) -> dict:
    """Fixed load increase every `increment_every_weeks` weeks."""
    increment = exercise_cfg.get("increment", 5.0)
    increment_every = exercise_cfg.get("increment_every_weeks", 1)
    base_load = exercise_cfg["load_value"]
    steps = (week_number - 1) // increment_every
    load = base_load + steps * increment
    return {
        "sets": exercise_cfg["sets"],
        "reps": exercise_cfg["reps"],
        "load_type": "external",
        "load_value": load,
    }


def apply_double_progression(exercise_cfg: dict, week_number: int) -> dict:
    """Reps climb by `rep_step` each week within [reps_low, reps_high]. On
    reaching reps_high, load increases by `load_increment` and reps reset to
    reps_low. If load_value is None (an unknown starting weight -- the
    generator's fallback case), load stays None throughout and only reps
    progress; the user fills in and tracks their own load by feel.
    """
    reps_low = exercise_cfg["reps_low"]
    reps_high = exercise_cfg["reps_high"]
    rep_step = exercise_cfg.get("rep_step", 1)
    load_increment = exercise_cfg.get("load_increment", 5.0)
    base_load = exercise_cfg.get("load_value")
    span = reps_high - reps_low
    weeks_per_cycle = (span // rep_step) + 1
    cycle_index = (week_number - 1) // weeks_per_cycle
    week_in_cycle = (week_number - 1) % weeks_per_cycle
    reps_current = reps_low + week_in_cycle * rep_step
    load = None if base_load is None else base_load + cycle_index * load_increment
    return {
        "sets": exercise_cfg["sets"],
        "reps": f"{reps_current}",
        "load_type": "external",
        "load_value": load,
    }


def apply_variation_ladder(exercise_cfg: dict, week_number: int, ladder: list) -> dict:
    """Climb one rung of `ladder` (ordered easiest -> hardest, sharing a
    ladder_group) every `weeks_per_rung` weeks, capped at the top rung.
    """
    weeks_per_rung = exercise_cfg.get("weeks_per_rung", 2)
    rung_index = min((week_number - 1) // weeks_per_rung, len(ladder) - 1)
    rung = ladder[rung_index]
    return {
        "exercise_id": rung["exercise_id"],
        "name": rung["name"],
        "sets": exercise_cfg["sets"],
        "reps": rung["default_reps"],
        "load_type": "bodyweight",
        "load_value": None,
    }


def generate_block(exercise_cfg: dict, block_weeks: int, model: str, ladder=None) -> list:
    """Return one entry per week (1..block_weeks) for this exercise."""
    if model not in PROGRESSION_MODELS:
        raise ValueError(f"unknown progression model: {model}")
    weeks = []
    for w in range(1, block_weeks + 1):
        if model == "linear":
            weeks.append(apply_linear(exercise_cfg, w))
        elif model == "double-progression":
            weeks.append(apply_double_progression(exercise_cfg, w))
        elif model == "variation-ladder":
            if not ladder:
                raise ValueError("variation-ladder model requires a ladder")
            weeks.append(apply_variation_ladder(exercise_cfg, w, ladder))
    return weeks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_progression.py -v`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/workout/lib/progression.py plugins/workout/lib/tests/test_progression.py
git commit -m "feat(workout): add progression engine (linear, double-progression, variation-ladder)"
```

---

## Task 7: Curated templates

**Files:**
- Create: `plugins/workout/references/templates/bodyweight_beginner_3day.json`
- Create: `plugins/workout/references/templates/dumbbell_beginner_3day.json`
- Create: `plugins/workout/lib/templates.py`
- Test: `plugins/workout/lib/tests/test_templates.py`

**Interfaces:**
- Consumes: nothing beyond the JSON files it loads.
- Produces: `load_template(path) -> dict`, `load_all_templates(templates_dir=None) -> list[dict]`, `match_template(templates, level, equipment_ids, days_per_week) -> dict | None`. A template dict has keys: `template_id, level, goal, days_per_week, session_minutes, required_equipment, progression_model, block_weeks, sessions` where each session has `day, label, exercises` and each exercise entry is either a ladder entry (`ladder_group, sets, weeks_per_rung, tempo, rest, notes`) or a loaded entry (`exercise_id, sets, reps_low, reps_high, rep_step, load_value, load_increment, tempo, rest, notes`).

- [ ] **Step 1: Write the bodyweight template**

Create `plugins/workout/references/templates/bodyweight_beginner_3day.json`:

```json
{
  "template_id": "bodyweight_beginner_3day",
  "level": "beginner",
  "goal": "general_strength",
  "days_per_week": 3,
  "session_minutes": 30,
  "required_equipment": ["sturdy_table"],
  "progression_model": "variation-ladder",
  "block_weeks": 8,
  "sessions": [
    {
      "day": 1,
      "label": "Full Body A",
      "exercises": [
        {"ladder_group": "squat_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s", "notes": "Sit the hips back; keep the chest tall."},
        {"ladder_group": "push_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s", "notes": "Keep the body in a straight line, elbows ~45 degrees from the torso."},
        {"ladder_group": "core_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "n/a", "rest": "30s", "notes": "Move slowly; keep the low back pressed to the floor."}
      ]
    },
    {
      "day": 2,
      "label": "Full Body B",
      "exercises": [
        {"ladder_group": "hinge_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s", "notes": "Squeeze the glutes at the top; avoid arching the low back."},
        {"ladder_group": "pull_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s", "notes": "Use a sturdy table; pull the chest toward the table edge."},
        {"ladder_group": "core_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "n/a", "rest": "30s", "notes": "Move slowly; keep the low back pressed to the floor."}
      ]
    },
    {
      "day": 3,
      "label": "Full Body C",
      "exercises": [
        {"ladder_group": "squat_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s", "notes": "Sit the hips back; keep the chest tall."},
        {"ladder_group": "push_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s", "notes": "Keep the body in a straight line, elbows ~45 degrees from the torso."},
        {"ladder_group": "hinge_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s", "notes": "Squeeze the glutes at the top; avoid arching the low back."}
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the dumbbell template**

Create `plugins/workout/references/templates/dumbbell_beginner_3day.json`:

```json
{
  "template_id": "dumbbell_beginner_3day",
  "level": "beginner",
  "goal": "general_strength",
  "days_per_week": 3,
  "session_minutes": 40,
  "required_equipment": ["dumbbell"],
  "progression_model": "double-progression",
  "block_weeks": 8,
  "sessions": [
    {
      "day": 1,
      "label": "Full Body A",
      "exercises": [
        {"exercise_id": "db_goblet_squat", "sets": 3, "reps_low": 8, "reps_high": 12, "rep_step": 1, "load_value": 15.0, "load_increment": 5.0, "tempo": "3-0-1", "rest": "90s", "notes": "Hold one dumbbell vertically at the chest."},
        {"exercise_id": "db_bench_press_floor", "sets": 3, "reps_low": 8, "reps_high": 12, "rep_step": 1, "load_value": 15.0, "load_increment": 5.0, "tempo": "2-0-2", "rest": "90s", "notes": "Lie on the floor; press dumbbells straight up over the shoulders."},
        {"exercise_id": "db_farmer_carry", "sets": 3, "reps_low": 2, "reps_high": 4, "rep_step": 1, "load_value": 20.0, "load_increment": 5.0, "tempo": "n/a", "rest": "60s", "notes": "Trips of ~30m each; walk tall, shoulders back."}
      ]
    },
    {
      "day": 2,
      "label": "Full Body B",
      "exercises": [
        {"exercise_id": "db_romanian_deadlift", "sets": 3, "reps_low": 8, "reps_high": 12, "rep_step": 1, "load_value": 15.0, "load_increment": 5.0, "tempo": "3-1-1", "rest": "90s", "notes": "Hinge at the hips, dumbbells stay close to the legs."},
        {"exercise_id": "db_bent_over_row", "sets": 3, "reps_low": 8, "reps_high": 12, "rep_step": 1, "load_value": 15.0, "load_increment": 5.0, "tempo": "2-0-2", "rest": "90s", "notes": "Hinge forward ~45 degrees; pull the elbows past the ribs."},
        {"exercise_id": "db_farmer_carry", "sets": 3, "reps_low": 2, "reps_high": 4, "rep_step": 1, "load_value": 20.0, "load_increment": 5.0, "tempo": "n/a", "rest": "60s", "notes": "Trips of ~30m each; walk tall, shoulders back."}
      ]
    },
    {
      "day": 3,
      "label": "Full Body C",
      "exercises": [
        {"exercise_id": "db_goblet_squat", "sets": 3, "reps_low": 8, "reps_high": 12, "rep_step": 1, "load_value": 15.0, "load_increment": 5.0, "tempo": "3-0-1", "rest": "90s", "notes": "Hold one dumbbell vertically at the chest."},
        {"exercise_id": "db_bent_over_row", "sets": 3, "reps_low": 8, "reps_high": 12, "rep_step": 1, "load_value": 15.0, "load_increment": 5.0, "tempo": "2-0-2", "rest": "90s", "notes": "Hinge forward ~45 degrees; pull the elbows past the ribs."},
        {"exercise_id": "db_romanian_deadlift", "sets": 3, "reps_low": 8, "reps_high": 12, "rep_step": 1, "load_value": 15.0, "load_increment": 5.0, "tempo": "3-1-1", "rest": "90s", "notes": "Hinge at the hips, dumbbells stay close to the legs."}
      ]
    }
  ]
}
```

- [ ] **Step 3: Write the failing tests**

Create `plugins/workout/lib/tests/test_templates.py`:

```python
import templates as tpl_mod


SAMPLE_TEMPLATES = [
    {"template_id": "a", "level": "beginner", "days_per_week": 3, "required_equipment": []},
    {"template_id": "b", "level": "beginner", "days_per_week": 3, "required_equipment": ["dumbbell"]},
    {"template_id": "c", "level": "intermediate", "days_per_week": 3, "required_equipment": ["dumbbell"]},
    {"template_id": "d", "level": "beginner", "days_per_week": 4, "required_equipment": []},
]


def test_match_prefers_more_tailored_template():
    match = tpl_mod.match_template(SAMPLE_TEMPLATES, "beginner", {"dumbbell", "sled"}, 3)
    assert match["template_id"] == "b"


def test_match_falls_back_when_equipment_missing():
    match = tpl_mod.match_template(SAMPLE_TEMPLATES, "beginner", set(), 3)
    assert match["template_id"] == "a"


def test_match_respects_level_and_days():
    assert tpl_mod.match_template(SAMPLE_TEMPLATES, "advanced", {"dumbbell"}, 3) is None
    assert tpl_mod.match_template(SAMPLE_TEMPLATES, "beginner", {"dumbbell"}, 7) is None


def test_load_all_templates_reads_real_files():
    loaded = tpl_mod.load_all_templates()
    ids = {t["template_id"] for t in loaded}
    assert {"bodyweight_beginner_3day", "dumbbell_beginner_3day"}.issubset(ids)
    for t in loaded:
        assert t["progression_model"] in {"double-progression", "linear", "variation-ladder"}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_templates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'templates'`

- [ ] **Step 5: Implement the template loader**

Create `plugins/workout/lib/templates.py`:

```python
"""Curated template loading and matching."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "references" / "templates"


def load_template(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all_templates(templates_dir=None) -> list:
    templates_dir = templates_dir or TEMPLATES_DIR
    return [load_template(p) for p in sorted(Path(templates_dir).glob("*.json"))]


def match_template(templates: list, level: str, equipment_ids, days_per_week: int):
    """Return the best-fit template, or None if no template qualifies.

    A template qualifies if its level and days_per_week match exactly and
    its required_equipment is fully covered by equipment_ids. Among
    qualifying templates, prefer the one requiring the most equipment (the
    most "tailored" fit) as a simple tie-breaker.
    """
    equipment_ids = set(equipment_ids)
    candidates = [
        t for t in templates
        if t["level"] == level
        and t["days_per_week"] == days_per_week
        and set(t.get("required_equipment", [])).issubset(equipment_ids)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda t: len(t.get("required_equipment", [])))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_templates.py -v`
Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
git add plugins/workout/references/templates/bodyweight_beginner_3day.json \
    plugins/workout/references/templates/dumbbell_beginner_3day.json \
    plugins/workout/lib/templates.py plugins/workout/lib/tests/test_templates.py
git commit -m "feat(workout): add curated beginner templates and template matching"
```

---

## Task 8: Program generator

**Files:**
- Create: `plugins/workout/lib/generator.py`
- Test: `plugins/workout/lib/tests/test_generator.py`

**Interfaces:**
- Consumes: `model.Program/ProgramMeta/Progression/Week/Session/ProgramExercise/LoadSpec` (Task 2), `exercises.filter_exercises/group_by_pattern/ladder_for_group/find_by_id` (Task 4), `progression.generate_block` (Task 6).
- Produces: `template_is_constraint_compatible(template, exercises, excluded_constraints) -> bool`, `build_program_from_template(template, exercises, equipment_profile, constraints, created) -> Program`, `generate_program(exercises, equipment_profile, constraints, level, days_per_week, session_minutes, block_weeks, created, goal="general_strength") -> Program`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/workout/lib/tests/test_generator.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator'`

- [ ] **Step 3: Implement the generator**

Create `plugins/workout/lib/generator.py`:

```python
"""Program generation: builds a full Program either from a curated template
(templates.py) or, when no template fits the user's equipment/constraints,
by assembling one from the eligible exercise pool directly.
"""
from __future__ import annotations

from model import Program, ProgramMeta, Progression, Week, Session, ProgramExercise, LoadSpec
import exercises as exercises_mod
import progression as progression_mod

PATTERN_ORDER = ("squat", "hinge", "push", "pull", "core", "carry")
DEFAULT_WEEKS_PER_RUNG = 2
DEFAULT_SETS = 3
DEFAULT_REPS_LOW = 8
DEFAULT_REPS_HIGH = 12
DEFAULT_REP_STEP = 1
DEFAULT_LOAD_INCREMENT = 5.0


def template_is_constraint_compatible(template: dict, exercises: list, excluded_constraints) -> bool:
    """A template can only be used if every exercise slot has at least one
    option (a ladder rung, or the fixed exercise) that avoids every excluded
    constraint flag."""
    excluded = set(excluded_constraints)
    for session in template["sessions"]:
        for entry in session["exercises"]:
            if "ladder_group" in entry:
                ladder = exercises_mod.ladder_for_group(exercises, entry["ladder_group"])
                if not any(not (set(r.get("constraint_flags", [])) & excluded) for r in ladder):
                    return False
            else:
                ex = exercises_mod.find_by_id(exercises, entry["exercise_id"])
                if set(ex.get("constraint_flags", [])) & excluded:
                    return False
    return True


def _build_ladder_exercise(entry: dict, exercises: list, block_weeks: int) -> list:
    ladder = exercises_mod.ladder_for_group(exercises, entry["ladder_group"])
    weeks = progression_mod.generate_block(entry, block_weeks, "variation-ladder", ladder=ladder)
    movement_pattern = ladder[0]["movement_pattern"]
    rule = f"Progress to the next ladder rung every {entry['weeks_per_rung']} weeks."
    result = []
    for step in weeks:
        result.append(ProgramExercise(
            exercise_id=step["exercise_id"], name=step["name"], movement_pattern=movement_pattern,
            sets=entry["sets"], reps=step["reps"], load=LoadSpec(type="bodyweight", progression_rule=rule),
            tempo=entry["tempo"], rest=entry["rest"], notes=entry.get("notes", ""),
        ))
    return result


def _build_loaded_exercise(entry: dict, exercises: list, block_weeks: int, model_name: str) -> list:
    ex_meta = exercises_mod.find_by_id(exercises, entry["exercise_id"])
    weeks = progression_mod.generate_block(entry, block_weeks, model_name)
    if model_name == "double-progression":
        rule = (
            f"Add a rep each week; at {entry['reps_high']} reps for all sets, "
            f"add {entry['load_increment']}lb and reset to {entry['reps_low']} reps."
        )
    else:
        rule = (
            f"Add {entry.get('increment', DEFAULT_LOAD_INCREMENT)}lb every "
            f"{entry.get('increment_every_weeks', 1)} week(s)."
        )
    result = []
    for step in weeks:
        result.append(ProgramExercise(
            exercise_id=entry["exercise_id"], name=ex_meta["name"],
            movement_pattern=ex_meta["movement_pattern"], sets=entry["sets"], reps=step["reps"],
            load=LoadSpec(type="external", value=step["load_value"], progression_rule=rule),
            tempo=entry["tempo"], rest=entry["rest"], notes=entry.get("notes", ""),
        ))
    return result


def build_program_from_template(template: dict, exercises: list, equipment_profile: list,
                                 constraints: list, created: str) -> Program:
    block_weeks = template["block_weeks"]
    model_name = template["progression_model"]

    per_slot_weeks = []
    for session in template["sessions"]:
        slot_series = []
        for entry in session["exercises"]:
            if "ladder_group" in entry:
                slot_series.append(_build_ladder_exercise(entry, exercises, block_weeks))
            else:
                slot_series.append(_build_loaded_exercise(entry, exercises, block_weeks, model_name))
        per_slot_weeks.append((session["day"], session["label"], slot_series))

    weeks = []
    for week_number in range(1, block_weeks + 1):
        sessions = []
        for day, label, slot_series in per_slot_weeks:
            week_exercises = [series[week_number - 1] for series in slot_series]
            sessions.append(Session(day=day, label=label, exercises=week_exercises))
        weeks.append(Week(number=week_number, sessions=sessions))

    meta = ProgramMeta(
        level=template["level"], goal=template["goal"], days_per_week=template["days_per_week"],
        session_minutes=template["session_minutes"], equipment_profile=list(equipment_profile),
        constraints=list(constraints), created=created, source=template["template_id"],
    )
    return Program(meta=meta, progression=Progression(model=model_name, block_weeks=block_weeks), weeks=weeks)


def _pick_representative(pool: list) -> dict:
    """Deterministic pick: prefer a ladder-rank-0 bodyweight starting point,
    else the alphabetically-first exercise_id."""
    rank_zero = [e for e in pool if e.get("ladder_rank") == 0]
    candidates = rank_zero if rank_zero else pool
    return sorted(candidates, key=lambda e: e["exercise_id"])[0]


def generate_program(exercises: list, equipment_profile: list, constraints: list, level: str,
                      days_per_week: int, session_minutes: int, block_weeks: int, created: str,
                      goal: str = "general_strength") -> Program:
    """Assemble a program directly from the eligible exercise pool. Used when
    no curated template fits the user's equipment or active constraints, or
    when the user explicitly asks to remix.

    Generated loaded exercises are left with load_value=None for week 1 --
    the user fills in a starting weight by feel (leave 2+ reps in reserve)
    rather than the generator guessing a one-size-fits-all number.
    """
    eligible = exercises_mod.filter_exercises(exercises, equipment_profile, constraints)
    grouped = exercises_mod.group_by_pattern(eligible)

    representatives = {}
    for pattern in PATTERN_ORDER:
        pool = grouped.get(pattern, [])
        if pool:
            representatives[pattern] = _pick_representative(pool)

    patterns_with_options = [p for p in PATTERN_ORDER if p in representatives]
    per_slot_weeks = []
    for day in range(1, days_per_week + 1):
        slot_series = []
        for pattern in patterns_with_options[:5]:
            ex = representatives[pattern]
            if ex.get("ladder_group"):
                entry = {"ladder_group": ex["ladder_group"], "sets": DEFAULT_SETS,
                         "weeks_per_rung": DEFAULT_WEEKS_PER_RUNG, "tempo": "2-0-2", "rest": "60s",
                         "notes": ex.get("notes", "")}
                slot_series.append(_build_ladder_exercise(entry, exercises, block_weeks))
            else:
                entry = {"exercise_id": ex["exercise_id"], "sets": DEFAULT_SETS,
                         "reps_low": DEFAULT_REPS_LOW, "reps_high": DEFAULT_REPS_HIGH,
                         "rep_step": DEFAULT_REP_STEP, "load_value": None,
                         "load_increment": DEFAULT_LOAD_INCREMENT, "tempo": "2-0-2", "rest": "90s",
                         "notes": ex.get("notes", "")}
                slot_series.append(_build_loaded_exercise(entry, exercises, block_weeks, "double-progression"))
        per_slot_weeks.append((day, f"Session {day}", slot_series))

    weeks = []
    for week_number in range(1, block_weeks + 1):
        sessions = []
        for day, label, slot_series in per_slot_weeks:
            week_exercises = [series[week_number - 1] for series in slot_series]
            sessions.append(Session(day=day, label=label, exercises=week_exercises))
        weeks.append(Week(number=week_number, sessions=sessions))

    meta = ProgramMeta(
        level=level, goal=goal, days_per_week=days_per_week, session_minutes=session_minutes,
        equipment_profile=list(equipment_profile), constraints=list(constraints), created=created,
        source="generated",
    )
    return Program(
        meta=meta, progression=Progression(model="double-progression", block_weeks=block_weeks), weeks=weeks
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_generator.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/workout/lib/generator.py plugins/workout/lib/tests/test_generator.py
git commit -m "feat(workout): add program generator with constraint-aware template fallback"
```

---

## Task 9: Renderers (markdown, CSV, JSON)

**Files:**
- Create: `plugins/workout/lib/render.py`
- Test: `plugins/workout/lib/tests/test_render.py`

**Interfaces:**
- Consumes: `model.Program` (Task 2).
- Produces: `render_markdown(program) -> str`, `render_csv(program) -> str`, `render_json(program) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/workout/lib/tests/test_render.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'render'`

- [ ] **Step 3: Implement the renderers**

Create `plugins/workout/lib/render.py`:

```python
"""Renderers: pure functions that turn a Program into printable output. No
business logic here -- the program is already fully computed.
"""
from __future__ import annotations

import csv
import io
import json

from model import Program


def _fmt_load(load) -> str:
    if load.type == "bodyweight":
        return "Bodyweight"
    if load.value is None:
        return "____ lb (start light, log it)"
    return f"{load.value:g} lb"


def render_markdown(program: Program) -> str:
    meta = program.meta
    out = io.StringIO()
    out.write(f"# {program.progression.block_weeks}-Week Home Strength Program — {meta.level.title()}\n\n")
    out.write(
        f"**Goal:** {meta.goal.replace('_', ' ').title()}  \n"
        f"**Days/week:** {meta.days_per_week}  \n"
        f"**Session length:** ~{meta.session_minutes} min  \n"
        f"**Equipment:** {', '.join(meta.equipment_profile) or 'bodyweight only'}  \n"
        f"**Constraints honored:** {', '.join(meta.constraints) or 'none'}  \n"
        f"**Source:** {meta.source}  \n"
        f"**Progression model:** {program.progression.model}\n\n"
    )
    for week in program.weeks:
        out.write(f"## Week {week.number}\n\n")
        for session in week.sessions:
            out.write(f"### Day {session.day} — {session.label}\n\n")
            out.write("| Exercise | Sets | Reps | Load | Tempo | Rest | Done | Actual reps | RPE | Notes |\n")
            out.write("|---|---|---|---|---|---|---|---|---|---|\n")
            for ex in session.exercises:
                out.write(
                    f"| {ex.name} | {ex.sets} | {ex.reps} | {_fmt_load(ex.load)} | {ex.tempo} | "
                    f"{ex.rest} | [ ] | ____ | ____ | {ex.notes} |\n"
                )
            out.write("\n")
    return out.getvalue()


def render_csv(program: Program) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "week", "day", "session_label", "exercise", "sets", "target_reps", "load_type",
        "load_value", "tempo", "rest", "notes", "actual_reps", "actual_load", "rpe", "pain",
    ])
    for week in program.weeks:
        for session in week.sessions:
            for ex in session.exercises:
                writer.writerow([
                    week.number, session.day, session.label, ex.name, ex.sets, ex.reps,
                    ex.load.type, "" if ex.load.value is None else ex.load.value, ex.tempo,
                    ex.rest, ex.notes, "", "", "", "",
                ])
    return out.getvalue()


def render_json(program: Program) -> str:
    return json.dumps(program.to_dict(), indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_render.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/workout/lib/render.py plugins/workout/lib/tests/test_render.py
git commit -m "feat(workout): add markdown, CSV, and JSON renderers"
```

---

## Task 10: Source index and SQLite seeding

**Files:**
- Create: `plugins/workout/references/sources.md`
- Create: `plugins/workout/lib/seed.py`
- Test: `plugins/workout/lib/tests/test_seed.py`
- Modify: `plugins/workout/lib/store.py` (wire auto-seeding into `connect()`)
- Modify: `plugins/workout/lib/tests/test_store.py` (append 2 tests for the new auto-seed behavior)

**Interfaces:**
- Consumes: `store.connect` (Task 3, for tests only).
- Produces: `seed_exercises(conn, path=None) -> int`, `seed_equipment_catalog(conn, path=None) -> int`, `parse_sources_md(text) -> list[dict]`, `seed_sources(conn, path=None) -> int`, `seed_all(conn) -> dict`. Also modifies `store.connect` (Task 3) so every fresh database is auto-seeded from `references/` -- the git-versioned content becomes queryable from SQLite immediately, matching the design spec's "seeded into SQLite on init."

- [ ] **Step 1: Write the source index**

Create `plugins/workout/references/sources.md`:

```markdown
# Workout Plugin — Source Index

Vetted methodology and evidence sources behind the templates, progression
engine, and constraint-aware substitution logic in this plugin. Each entry
below is seeded into the `sources` table by `lib/seed.py`.

## acsm_progression_models
- title: Progression Models in Resistance Training for Healthy Adults (ACSM Position Stand)
- author_org: American College of Sports Medicine
- url: https://pubmed.ncbi.nlm.nih.gov/19204579/
- topic_tags: progression, reps-ranges, program-design
- trust_tier: high
- informs: progression.py double-progression model, novice 8-12 rep range defaults

## nsca_foundations_programming
- title: Foundations of Fitness Programming
- author_org: National Strength and Conditioning Association
- url: https://www.nsca.com/contentassets/8323553f698a466a98220b21d9eb9a65/foundationsoffitnessprogramming_201508.pdf
- topic_tags: progressive-overload, program-design
- trust_tier: high
- informs: overall program structure, progressive-overload sequencing

## bodyweightfitness_recommended_routine
- title: Recommended Routine and Strength Training wiki
- author_org: r/bodyweightfitness community (The Fitness Wiki)
- url: https://thefitness.wiki/routines/
- topic_tags: bodyweight, beginner, variation-ladder
- trust_tier: medium
- informs: bodyweight_beginner_3day template, variation-ladder progression model

## autoregulation_rpe_systematic_review
- title: Effects of subjective and objective autoregulation methods for intensity and volume on enhancing maximal strength during resistance-training interventions
- author_org: PeerJ (systematic review)
- url: https://peerj.com/articles/10663/
- topic_tags: rpe, autoregulation, pain-cap
- trust_tier: high
- informs: RPE/pain-cap autoregulation in the progression engine

## hsr_vs_eccentric_achilles_rct
- title: Heavy Slow Resistance Versus Eccentric Training as Treatment for Achilles Tendinopathy
- author_org: PubMed (RCT)
- url: https://pubmed.ncbi.nlm.nih.gov/26018970/
- topic_tags: tendinopathy, heavy-slow-resistance, rehab-loading
- trust_tier: high
- informs: constraint-aware loading defaults, tempo conventions (3-0-1 style)

## isometric_eccentric_hsr_systematic_review
- title: Effects of isometric, eccentric, or heavy slow resistance exercises on pain and function in individuals with patellar tendinopathy
- author_org: PubMed (systematic review)
- url: https://pubmed.ncbi.nlm.nih.gov/29972281/
- topic_tags: tendinopathy, isometrics, rehab-loading
- trust_tier: high
- informs: constraint-aware exercise substitution, arm-load/grip flag design

## putting_heavy_into_hsr
- title: Putting "Heavy" into Heavy Slow Resistance
- author_org: PubMed
- url: https://pubmed.ncbi.nlm.nih.gov/35084703/
- topic_tags: heavy-slow-resistance, tempo, load-progression
- trust_tier: medium
- informs: linear and double-progression load-increment defaults

## eccentric_lateral_elbow_tendinopathy_review
- title: The Beneficial Effects of Eccentric Exercise in the Management of Lateral Elbow Tendinopathy
- author_org: PubMed (review)
- url: https://pubmed.ncbi.nlm.nih.gov/34501416/
- topic_tags: tendinopathy, elbow, constraint-aware
- trust_tier: medium
- informs: arm-load / grip constraint flags, arm-free lower-body substitution (sled, belt squat, weighted vest)
```

- [ ] **Step 2: Write the failing tests**

Create `plugins/workout/lib/tests/test_seed.py`:

```python
import store
import seed


def test_seed_exercises_populates_table_from_real_references():
    conn = store.connect(":memory:")
    count = seed.seed_exercises(conn)
    rows = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    assert count == rows
    assert count >= 20


def test_seed_equipment_catalog_populates_table():
    conn = store.connect(":memory:")
    count = seed.seed_equipment_catalog(conn)
    rows = conn.execute("SELECT COUNT(*) FROM equipment_catalog").fetchone()[0]
    assert count == rows
    assert count >= 5


def test_parse_sources_md_extracts_fields():
    text = (
        "## example_source\n"
        "- title: Example Title\n"
        "- author_org: Example Org\n"
        "- url: https://example.com/paper\n"
        "- topic_tags: a, b\n"
        "- trust_tier: high\n"
        "- informs: some.py\n"
    )
    entries = seed.parse_sources_md(text)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["source_id"] == "example_source"
    assert entry["title"] == "Example Title"
    assert entry["topic_tags"] == ["a", "b"]


def test_parse_sources_md_handles_multiple_entries():
    text = (
        "## first\n- title: First\n- author_org: Org\n- url: https://a.example\n"
        "- topic_tags: x\n- trust_tier: high\n- informs: a\n"
        "\n## second\n- title: Second\n- author_org: Org\n- url: https://b.example\n"
        "- topic_tags: y\n- trust_tier: medium\n- informs: b\n"
    )
    entries = seed.parse_sources_md(text)
    assert [e["source_id"] for e in entries] == ["first", "second"]


def test_seed_sources_populates_table_from_real_references():
    conn = store.connect(":memory:")
    count = seed.seed_sources(conn)
    rows = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    assert count == rows
    assert count >= 5


def test_seed_all_seeds_every_table():
    conn = store.connect(":memory:")
    counts = seed.seed_all(conn)
    assert set(counts) == {"exercises", "equipment_catalog", "sources"}
    assert all(v > 0 for v in counts.values())
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_seed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'seed'`

- [ ] **Step 4: Implement seeding**

Create `plugins/workout/lib/seed.py`:

```python
"""Seed the SQLite store's reference tables from the git-versioned
references/ content: exercises.json, equipment.json, sources.md.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"


def seed_exercises(conn: sqlite3.Connection, path=None) -> int:
    path = path or (REFERENCES_DIR / "exercises.json")
    with open(path, encoding="utf-8") as f:
        exercises = json.load(f)
    conn.execute("DELETE FROM exercises")
    conn.executemany(
        """INSERT INTO exercises
           (exercise_id, name, movement_pattern, equipment_required, constraint_flags,
            ladder_group, ladder_rank, default_reps, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                e["exercise_id"], e["name"], e["movement_pattern"],
                json.dumps(e.get("equipment_required", [])), json.dumps(e.get("constraint_flags", [])),
                e.get("ladder_group"), e.get("ladder_rank"), e["default_reps"], e.get("notes", ""),
            )
            for e in exercises
        ],
    )
    conn.commit()
    return len(exercises)


def seed_equipment_catalog(conn: sqlite3.Connection, path=None) -> int:
    path = path or (REFERENCES_DIR / "equipment.json")
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    conn.execute("DELETE FROM equipment_catalog")
    conn.executemany(
        """INSERT INTO equipment_catalog
           (equipment_id, name, cost_tier, space_tier, approx_cost_usd, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (i["equipment_id"], i["name"], i["cost_tier"], i["space_tier"], i["approx_cost_usd"],
             i.get("notes", ""))
            for i in items
        ],
    )
    conn.commit()
    return len(items)


_SOURCE_ENTRY_RE = re.compile(
    r"^##\s+(?P<source_id>\S+)\s*\n"
    r"(?P<body>.*?)(?=\n##\s+\S+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_FIELD_RE = re.compile(r"^-\s+(?P<key>[a-z_]+):\s*(?P<value>.*)$", re.MULTILINE)


def parse_sources_md(text: str) -> list:
    """Parse references/sources.md's `## id` + `- field: value` entries."""
    entries = []
    for match in _SOURCE_ENTRY_RE.finditer(text):
        source_id = match.group("source_id")
        body = match.group("body")
        fields = {m.group("key"): m.group("value").strip() for m in _FIELD_RE.finditer(body)}
        entries.append({
            "source_id": source_id,
            "title": fields.get("title", ""),
            "author_org": fields.get("author_org", ""),
            "url": fields.get("url", ""),
            "topic_tags": [t.strip() for t in fields.get("topic_tags", "").split(",") if t.strip()],
            "trust_tier": fields.get("trust_tier", ""),
            "informs": [t.strip() for t in fields.get("informs", "").split(",") if t.strip()],
        })
    return entries


def seed_sources(conn: sqlite3.Connection, path=None) -> int:
    path = path or (REFERENCES_DIR / "sources.md")
    with open(path, encoding="utf-8") as f:
        entries = parse_sources_md(f.read())
    conn.execute("DELETE FROM sources")
    conn.executemany(
        """INSERT INTO sources (source_id, title, author_org, url, topic_tags, trust_tier, informs)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (e["source_id"], e["title"], e["author_org"], e["url"], json.dumps(e["topic_tags"]),
             e["trust_tier"], json.dumps(e["informs"]))
            for e in entries
        ],
    )
    conn.commit()
    return len(entries)


def seed_all(conn: sqlite3.Connection) -> dict:
    return {
        "exercises": seed_exercises(conn),
        "equipment_catalog": seed_equipment_catalog(conn),
        "sources": seed_sources(conn),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_seed.py -v`
Expected: `6 passed`

- [ ] **Step 6: Wire auto-seeding into `store.connect()`**

Right now `seed.py` exists but nothing ever calls it against a real
database -- the `exercises`, `equipment_catalog`, and `sources` tables
would stay empty forever outside of tests. Fix this by having `connect()`
seed automatically the first time it sees an empty `exercises` table (safe
to call on every connect: it's a no-op once seeded, and it never touches
`programs`/`sessions`/`program_exercises`/`equipment_profile`, so user data
is never overwritten).

In `plugins/workout/lib/store.py`, replace:

```python
def connect(db_path=None) -> sqlite3.Connection:
    """Open (creating parent dirs as needed) and initialize the database."""
    path = Path(db_path) if db_path else default_db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn
```

with:

```python
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
```

- [ ] **Step 7: Add a test for the new auto-seed behavior**

Append to `plugins/workout/lib/tests/test_store.py`:

```python


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
```

- [ ] **Step 8: Run the full store test suite to verify everything still passes**

Run: `cd plugins/workout && python -m pytest lib/tests/test_store.py lib/tests/test_seed.py -v`
Expected: `14 passed` (`test_store.py` now has 8: the original 6 plus the 2 new auto-seed tests; `test_seed.py` has 6).

- [ ] **Step 9: Commit**

```bash
git add plugins/workout/references/sources.md plugins/workout/lib/seed.py \
    plugins/workout/lib/store.py plugins/workout/lib/tests/test_seed.py \
    plugins/workout/lib/tests/test_store.py
git commit -m "feat(workout): add source index, SQLite seeding, and auto-seed on connect"
```

---

## Task 11: Equipment advisor

**Files:**
- Create: `plugins/workout/lib/advisor.py`
- Test: `plugins/workout/lib/tests/test_advisor.py`

**Interfaces:**
- Consumes: `exercises.filter_exercises/group_by_pattern` (Task 4), `model.MOVEMENT_PATTERNS` (Task 2), `references/equipment.json` (Task 5).
- Produces: `load_equipment_catalog(path=None) -> list[dict]`, `pattern_coverage(exercises, equipment_ids, excluded_constraints) -> dict[str, int]`, `rank_equipment_gaps(exercises, catalog, owned_equipment_ids, excluded_constraints) -> list[dict]`, `thin_or_missing_patterns(exercises, equipment_ids, excluded_constraints, threshold=2) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/workout/lib/tests/test_advisor.py`:

```python
import advisor
import exercises as exercises_mod


SAMPLE_EXERCISES = [
    {"exercise_id": "bodyweight_squat", "movement_pattern": "squat", "equipment_required": [],
     "constraint_flags": []},
    {"exercise_id": "db_goblet_squat", "movement_pattern": "squat", "equipment_required": ["dumbbell"],
     "constraint_flags": ["grip"]},
    {"exercise_id": "table_inverted_row", "movement_pattern": "pull",
     "equipment_required": ["sturdy_table"], "constraint_flags": ["arm-load", "grip"]},
    {"exercise_id": "pullup_band_assisted", "movement_pattern": "pull",
     "equipment_required": ["pull_up_bar", "resistance_band"], "constraint_flags": ["arm-load", "grip"]},
]

SAMPLE_CATALOG = [
    {"equipment_id": "dumbbell", "name": "Dumbbells", "cost_tier": "medium", "space_tier": "small",
     "approx_cost_usd": 250},
    {"equipment_id": "pull_up_bar", "name": "Pull-Up Bar", "cost_tier": "low", "space_tier": "small",
     "approx_cost_usd": 30},
    {"equipment_id": "resistance_band", "name": "Resistance Band", "cost_tier": "low",
     "space_tier": "small", "approx_cost_usd": 30},
]


def test_pattern_coverage_counts_eligible_exercises_per_pattern():
    coverage = advisor.pattern_coverage(SAMPLE_EXERCISES, equipment_ids=[], excluded_constraints=[])
    assert coverage["squat"] == 1
    assert coverage.get("pull", 0) == 0


def test_rank_equipment_gaps_orders_by_unlock_score():
    ranked = advisor.rank_equipment_gaps(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=[], excluded_constraints=[]
    )
    ids = [r["equipment_id"] for r in ranked]
    assert "dumbbell" in ids
    dumbbell = next(r for r in ranked if r["equipment_id"] == "dumbbell")
    assert dumbbell["unlocks_exercise_count"] == 1
    assert dumbbell["unlocks_patterns"] == ["squat"]


def test_rank_equipment_gaps_excludes_already_owned_equipment():
    ranked = advisor.rank_equipment_gaps(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=["dumbbell"], excluded_constraints=[]
    )
    assert all(r["equipment_id"] != "dumbbell" for r in ranked)


def test_rank_equipment_gaps_respects_active_constraints():
    ranked = advisor.rank_equipment_gaps(
        SAMPLE_EXERCISES, SAMPLE_CATALOG, owned_equipment_ids=[],
        excluded_constraints=["arm-load", "grip"],
    )
    pull_up = next(r for r in ranked if r["equipment_id"] == "pull_up_bar")
    assert pull_up["unlocks_exercise_count"] == 0


def test_thin_or_missing_patterns_flags_uncovered_patterns():
    thin = advisor.thin_or_missing_patterns(SAMPLE_EXERCISES, equipment_ids=[], excluded_constraints=[])
    assert "pull" in thin


def test_real_catalog_and_exercises_produce_rankings():
    exercises = exercises_mod.load_exercises()
    catalog = advisor.load_equipment_catalog()
    ranked = advisor.rank_equipment_gaps(exercises, catalog, owned_equipment_ids=[], excluded_constraints=[])
    assert len(ranked) == len(catalog)
    assert ranked[0]["score"] >= ranked[-1]["score"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_advisor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'advisor'`

- [ ] **Step 3: Implement the advisor**

Create `plugins/workout/lib/advisor.py`:

```python
"""Equipment gap analysis: given what the user owns (and any active
constraints), rank equipment_catalog items by how much new eligible-exercise
value they'd unlock.
"""
from __future__ import annotations

import json
from pathlib import Path

from model import MOVEMENT_PATTERNS
import exercises as exercises_mod

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"

COST_WEIGHT = {"none": 4, "low": 3, "medium": 2, "high": 1}


def load_equipment_catalog(path=None) -> list:
    path = path or (REFERENCES_DIR / "equipment.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pattern_coverage(exercises: list, equipment_ids, excluded_constraints) -> dict:
    """Return {pattern: eligible_exercise_count} for every movement pattern."""
    eligible = exercises_mod.filter_exercises(exercises, equipment_ids, excluded_constraints)
    grouped = exercises_mod.group_by_pattern(eligible)
    return {pattern: len(items) for pattern, items in grouped.items()}


def rank_equipment_gaps(exercises: list, catalog: list, owned_equipment_ids, excluded_constraints) -> list:
    """Rank equipment the user doesn't yet own by how much new value adding
    it would unlock: how many currently-ineligible exercises become eligible,
    weighted by cost tier (cheaper + more unlocks ranks higher), with
    constraint-flagged exercises excluded from the unlock count (an item that
    only unlocks exercises the user's constraints rule out isn't actually
    useful to them right now).
    """
    owned = set(owned_equipment_ids)
    excluded = set(excluded_constraints)
    currently_eligible_ids = {
        e["exercise_id"] for e in exercises_mod.filter_exercises(exercises, owned, excluded)
    }

    results = []
    for item in catalog:
        equipment_id = item["equipment_id"]
        if equipment_id in owned:
            continue
        with_item = owned | {equipment_id}
        newly_eligible = [
            e for e in exercises_mod.filter_exercises(exercises, with_item, excluded)
            if e["exercise_id"] not in currently_eligible_ids
        ]
        unlocked_patterns = sorted({e["movement_pattern"] for e in newly_eligible})
        score = len(newly_eligible) * COST_WEIGHT.get(item["cost_tier"], 1)
        results.append({
            "equipment_id": equipment_id,
            "name": item["name"],
            "cost_tier": item["cost_tier"],
            "space_tier": item["space_tier"],
            "approx_cost_usd": item["approx_cost_usd"],
            "unlocks_exercise_count": len(newly_eligible),
            "unlocks_patterns": unlocked_patterns,
            "score": score,
        })
    return sorted(results, key=lambda r: r["score"], reverse=True)


def thin_or_missing_patterns(exercises: list, equipment_ids, excluded_constraints, threshold: int = 2) -> list:
    """Patterns with fewer than `threshold` eligible exercises -- worth
    flagging even before ranking specific equipment."""
    coverage = pattern_coverage(exercises, equipment_ids, excluded_constraints)
    return [p for p in MOVEMENT_PATTERNS if coverage.get(p, 0) < threshold]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_advisor.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/workout/lib/advisor.py plugins/workout/lib/tests/test_advisor.py
git commit -m "feat(workout): add equipment gap advisor"
```

---

## Task 12: equipment-intake skill

**Files:**
- Create: `plugins/workout/skills/equipment-intake/SKILL.md`
- Create: `plugins/workout/skills/equipment-intake/scripts/intake.py`

**Interfaces:**
- Consumes: `store.connect/save_equipment_profile/get_equipment_profile` (Task 3), `advisor.load_equipment_catalog` (Task 11).
- Produces: a CLI (`intake.py --list|--set|--show [--db PATH]`) that other skills' documentation refers to.

- [ ] **Step 1: Write the CLI script**

Create `plugins/workout/skills/equipment-intake/scripts/intake.py`:

```python
#!/usr/bin/env python3
"""CLI: record which equipment the user owns into the local SQLite store.

Usage:
    python intake.py --list                          # show all known equipment ids
    python intake.py --set dumbbell,pull_up_bar,sled  # replace the saved profile
    python intake.py --show                           # print the current profile
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import advisor  # noqa: E402
import store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list all known equipment ids and names")
    parser.add_argument("--set", metavar="IDS", help="comma-separated equipment_ids to save as the profile")
    parser.add_argument("--show", action="store_true", help="print the currently saved profile")
    parser.add_argument("--db", metavar="PATH", help="override the SQLite db path (mainly for tests)")
    args = parser.parse_args()

    conn = store.connect(args.db)

    if args.list:
        catalog = advisor.load_equipment_catalog()
        for item in catalog:
            print(f"{item['equipment_id']:20s} {item['name']}")
        return 0

    if args.set is not None:
        ids = [i.strip() for i in args.set.split(",") if i.strip()]
        store.save_equipment_profile(conn, ids, dt.date.today().isoformat())
        print(json.dumps({"saved": ids}))
        return 0

    if args.show:
        print(json.dumps({"equipment_profile": store.get_equipment_profile(conn)}))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write the skill documentation**

Create `plugins/workout/skills/equipment-intake/SKILL.md`:

```markdown
---
name: equipment-intake
version: 0.1.0
description: Record what home-gym equipment the user owns (and re-run whenever gear changes) so program-builder and equipment-advisor know what's available. Use when the user first sets up the workout plugin, or says things like "I just got a pull-up bar" or "update my equipment."
allowed-tools:
  - Bash
triggers:
  - what equipment do i have
  - update my equipment
  - i got a
  - set up my home gym
---

# equipment-intake

Collects a normalized equipment profile and saves it to the local SQLite store
(`lib/store.py`). This profile drives both `program-builder` (what exercises
are eligible) and `equipment-advisor` (what's worth buying next).

## Workflow

1. **Show the checklist.** Run:
   ```bash
   python3 skills/equipment-intake/scripts/intake.py --list
   ```
   Present the equipment as a grouped checklist to the user (bodyweight is
   always available; ask about bands, dumbbells, kettlebells, barbell+rack,
   bench, pull-up bar, weighted vest, sled, belt squat rig, sturdy table).

2. **Save the profile** once the user has answered:
   ```bash
   python3 skills/equipment-intake/scripts/intake.py --set dumbbell,pull_up_bar,sled
   ```

3. **Confirm** by showing it back:
   ```bash
   python3 skills/equipment-intake/scripts/intake.py --show
   ```

Re-run step 2 any time the user acquires or gets rid of equipment -- it fully
replaces the saved profile (it's not additive).

## Notes

- Equipment ids must match `references/equipment.json` -- use `--list` rather
  than guessing ids.
- This skill only stores *what's owned*. Physical constraints (e.g. "avoid
  grip-heavy exercises") are collected by `program-builder` at build time,
  not here -- they can change per-program while equipment ownership is
  durable.
```

- [ ] **Step 3: Smoke test the CLI**

Run:
```bash
cd plugins/workout
python skills/equipment-intake/scripts/intake.py --list --db /tmp/workout-smoke-test.db
```
Expected: 10 lines, one per equipment item, e.g. starting with `dumbbell              Adjustable Dumbbells (pair)`

Run:
```bash
python skills/equipment-intake/scripts/intake.py --set dumbbell,sled --db /tmp/workout-smoke-test.db
python skills/equipment-intake/scripts/intake.py --show --db /tmp/workout-smoke-test.db
```
Expected: `{"saved": ["dumbbell", "sled"]}` then `{"equipment_profile": ["dumbbell", "sled"]}`

- [ ] **Step 4: Commit**

```bash
git add plugins/workout/skills/equipment-intake/
git commit -m "feat(workout): add equipment-intake skill"
```

---

## Task 13: program-builder skill

**Files:**
- Create: `plugins/workout/skills/program-builder/SKILL.md`
- Create: `plugins/workout/skills/program-builder/scripts/build.py`

**Interfaces:**
- Consumes: `exercises.load_exercises` (Task 4), `templates.load_all_templates/match_template` (Task 7), `generator.template_is_constraint_compatible/build_program_from_template/generate_program` (Task 8), `render.render_markdown/render_csv/render_json` (Task 9), `model.validate_program/LEVELS` (Task 2), `store.connect/save_program` (Task 3).
- Produces: a CLI (`build.py --level --days --minutes [--equipment] [--constraints] [--block-weeks] --format --out [--db]`) and a reusable `build(level, days, minutes, equipment, constraints, block_weeks, conn) -> (Program, list[str])` function.

- [ ] **Step 1: Write the CLI script**

Create `plugins/workout/skills/program-builder/scripts/build.py`:

```python
#!/usr/bin/env python3
"""CLI: build a progressive home-strength program and write printable output.

Usage:
    python build.py --level beginner --days 3 --minutes 30 \
        --equipment dumbbell --constraints arm-load,grip \
        --block-weeks 8 --format markdown --out program.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import exercises as exercises_mod  # noqa: E402
import generator  # noqa: E402
import model  # noqa: E402
import render  # noqa: E402
import store  # noqa: E402
import templates as templates_mod  # noqa: E402


def build(level: str, days: int, minutes: int, equipment: list, constraints: list, block_weeks, conn):
    exercises = exercises_mod.load_exercises()
    all_templates = templates_mod.load_all_templates()
    match = templates_mod.match_template(all_templates, level, equipment, days)

    notes = []
    if match is not None and generator.template_is_constraint_compatible(match, exercises, constraints):
        if block_weeks and block_weeks != match["block_weeks"]:
            match = dict(match, block_weeks=block_weeks)
        program = generator.build_program_from_template(
            match, exercises, equipment_profile=equipment, constraints=constraints,
            created=dt.date.today().isoformat(),
        )
        notes.append(f"Used curated template: {match['template_id']}")
    else:
        reason = "no curated template matches this equipment/day count" if match is None else \
            "the closest template conflicts with your active constraints"
        notes.append(f"No template fit ({reason}); generated a program from the eligible exercise pool.")
        program = generator.generate_program(
            exercises, equipment_profile=equipment, constraints=constraints, level=level,
            days_per_week=days, session_minutes=minutes, block_weeks=block_weeks or 8,
            created=dt.date.today().isoformat(),
        )

    errors = model.validate_program(program)
    if errors:
        raise ValueError("generated program failed validation: " + "; ".join(errors))

    store.save_program(conn, program)
    return program, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", required=True, choices=list(model.LEVELS))
    parser.add_argument("--days", required=True, type=int)
    parser.add_argument("--minutes", required=True, type=int)
    parser.add_argument("--equipment", default="", help="comma-separated equipment_ids owned")
    parser.add_argument("--constraints", default="", help="comma-separated constraint flags to avoid")
    parser.add_argument("--block-weeks", type=int, default=None)
    parser.add_argument("--format", choices=["markdown", "csv", "json"], default="markdown")
    parser.add_argument("--out", required=True, help="output file path")
    parser.add_argument("--db", metavar="PATH", help="override the SQLite db path (mainly for tests)")
    args = parser.parse_args()

    equipment = [e.strip() for e in args.equipment.split(",") if e.strip()]
    constraints = [c.strip() for c in args.constraints.split(",") if c.strip()]

    conn = store.connect(args.db)
    program, notes = build(args.level, args.days, args.minutes, equipment, constraints,
                            args.block_weeks, conn)

    renderer = {"markdown": render.render_markdown, "csv": render.render_csv, "json": render.render_json}
    text = renderer[args.format](program)
    Path(args.out).write_text(text, encoding="utf-8")

    for note in notes:
        print(note)
    print(f"Wrote {args.format} program to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write the skill documentation**

Create `plugins/workout/skills/program-builder/SKILL.md`:

```markdown
---
name: program-builder
version: 0.1.0
description: Build a progressive, printable home-strength program from a curated template or generated from the eligible exercise pool, tailored to the user's equipment and any physical constraints. Use when the user asks for a workout program, wants to start training again "from near nothing," or wants to remix/regenerate their current program.
allowed-tools:
  - Bash
  - Read
triggers:
  - build me a workout program
  - give me a strength program
  - i want to start working out
  - remix my program
  - regenerate my program
---

# program-builder

Orchestrator. Turns (level, equipment, days/week, session length, active
constraints) into a full multi-week `Program`, persists it to SQLite, and
renders a printable output.

## Workflow

1. **Gather inputs conversationally:**
   - Level: `beginner` or `intermediate` (default `beginner` if the user
     describes starting from near nothing).
   - Days per week and session length in minutes.
   - Equipment: read from the saved profile
     (`equipment-intake`'s `--show`) unless the user wants to plan around a
     hypothetical/different set.
   - Constraints: any injury/physical limitation to design around, expressed
     as constraint flags -- `grip`, `arm-load`, `overhead`, `spinal-load`,
     `impact` (e.g. bilateral elbow tendinosis -> `grip,arm-load`).
   - Block length: how many weeks (default 8 if not specified).
   - Output format: `markdown` (default, printable tracker), `csv`
     (printable log grid), or `json` (interchange/backup).

2. **Build and render:**
   ```bash
   python3 skills/program-builder/scripts/build.py \
       --level beginner --days 3 --minutes 30 \
       --equipment dumbbell,pull_up_bar \
       --constraints grip,arm-load \
       --block-weeks 8 --format markdown --out program.md
   ```
   The script prints which curated template it used, or explains why it fell
   back to generating one (missing equipment, or the closest template
   conflicts with the stated constraints) -- relay that explanation to the
   user so they understand where their program came from.

3. **Deliver the output.** For `markdown`, offer to also produce it as an
   HTML artifact (styled, printable) via the `Artifact` tool -- follow the
   `artifact-design` skill's guidance when doing so. For `csv`, the file is
   meant to be printed and filled in by hand.

4. **Remix:** if the user doesn't like the result, re-run step 2 with a
   different equipment/constraint combination, or pass `--format json` and
   hand-edit specific exercises, then re-render with `render.py`'s functions
   (`lib/render.py`) for a quick one-off adjustment.

## Notes

- The output's `log` fields are intentionally blank in v1 -- this is a
  one-shot printable plan, not an adaptive one. See `lib/model.py`'s `log`
  field and the plugin design spec for the future adaptive/phone-logging
  direction.
- Every generated program is grounded in `references/sources.md` -- if the
  user asks "why is it built this way," look up the relevant `informs` tag
  there.
```

- [ ] **Step 3: Smoke test the CLI**

Run:
```bash
cd plugins/workout
python skills/program-builder/scripts/build.py \
    --level beginner --days 3 --minutes 30 --equipment dumbbell \
    --format markdown --out /tmp/workout-smoke-test.md --db /tmp/workout-smoke-test.db
```
Expected output includes: `Used curated template: dumbbell_beginner_3day` and `Wrote markdown program to /tmp/workout-smoke-test.md`

Run: `python -c "print(open('/tmp/workout-smoke-test.md').read()[:200])"`
Expected: starts with `# 8-Week Home Strength Program — Beginner`

Now test the constraint-driven generator fallback:
```bash
python skills/program-builder/scripts/build.py \
    --level beginner --days 3 --minutes 30 --equipment dumbbell \
    --constraints grip,arm-load --format json --out /tmp/workout-smoke-test2.json \
    --db /tmp/workout-smoke-test.db
```
Expected output includes: `No template fit (the closest template conflicts with your active constraints)`

- [ ] **Step 4: Commit**

```bash
git add plugins/workout/skills/program-builder/
git commit -m "feat(workout): add program-builder skill"
```

---

## Task 14: equipment-advisor skill

**Files:**
- Create: `plugins/workout/skills/equipment-advisor/SKILL.md`
- Create: `plugins/workout/skills/equipment-advisor/scripts/advise.py`

**Interfaces:**
- Consumes: `exercises.load_exercises` (Task 4), `advisor.load_equipment_catalog/thin_or_missing_patterns/rank_equipment_gaps` (Task 11).
- Produces: a CLI (`advise.py --owned --constraints --top`) plus a documented handoff protocol to `research`'s `literature-review` skill.

- [ ] **Step 1: Write the CLI script**

Create `plugins/workout/skills/equipment-advisor/scripts/advise.py`:

```python
#!/usr/bin/env python3
"""CLI: rank equipment gaps by how much new training value they'd unlock.

Usage:
    python advise.py --owned dumbbell,sled --constraints arm-load,grip
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import advisor  # noqa: E402
import exercises as exercises_mod  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owned", default="", help="comma-separated equipment_ids already owned")
    parser.add_argument("--constraints", default="", help="comma-separated constraint flags to avoid")
    parser.add_argument("--top", type=int, default=5, help="how many ranked recommendations to print")
    args = parser.parse_args()

    owned = [e.strip() for e in args.owned.split(",") if e.strip()]
    constraints = [c.strip() for c in args.constraints.split(",") if c.strip()]

    exercises = exercises_mod.load_exercises()
    catalog = advisor.load_equipment_catalog()

    thin = advisor.thin_or_missing_patterns(exercises, owned, constraints)
    ranked = advisor.rank_equipment_gaps(exercises, catalog, owned, constraints)[: args.top]

    print(json.dumps({"thin_or_missing_patterns": thin, "recommendations": ranked}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write the skill documentation**

Create `plugins/workout/skills/equipment-advisor/SKILL.md`:

```markdown
---
name: equipment-advisor
version: 0.1.0
description: Rank which piece of equipment would unlock the most new training value given what the user already owns and any active constraints, and hand off to the research plugin's literature-review skill when the user is ready to actually buy something. Use when the user asks what equipment to get next, or says something like "I'd like to get a squat rack."
allowed-tools:
  - Bash
  - Task
triggers:
  - what equipment should i buy
  - is it worth getting a
  - i want to get a squat rack
  - what should i add to my home gym
---

# equipment-advisor

Two jobs: (1) tell the user what's worth buying next, given what they
already own, and (2) once they've picked something, hand off to `research`'s
`literature-review` to find good-value specific products.

## Workflow

### 1. Gap analysis

```bash
python3 skills/equipment-advisor/scripts/advise.py \
    --owned dumbbell,sled --constraints arm-load,grip --top 5
```

Returns `thin_or_missing_patterns` (movement patterns with little/no eligible
coverage right now) and `recommendations` (equipment ranked by how many new
exercises it would unlock, weighted toward cheap + high-unlock items, with
constraint-flagged exercises excluded from the count -- so an item that would
only unlock exercises the user's injury rules out won't be recommended).

Present this conversationally: lead with the biggest gap, name the specific
equipment that best closes it, and note its approximate cost/space tier from
the output. Also mention if anything currently owned looks low-value for
their goals (YAGNI check) -- the advisor doesn't compute this automatically,
use judgment from the coverage numbers (e.g. redundant items within an
already well-covered pattern).

### 2. Research handoff (when the user wants to buy)

When the user says "I want to get a squat rack" (or similar), do **not**
recommend a specific product yourself -- hand off to the `research` plugin's
`literature-review` skill
(`plugins/research/skills/literature-review/SKILL.md`), passing a
`purchase`-intent query built from context:

- The equipment name and category
- Budget, if the user has stated one (otherwise use the `approx_cost_usd`
  from the advisor output as a starting anchor)
- Space constraints, if relevant
- Any preference surfaced by active constraints (e.g. "must not require
  gripping a handle under load" for someone avoiding `grip`/`arm-load`)

Example query to hand off: *"Best value squat rack for a home garage gym,
budget around $400, need it to fit in a single-car garage bay."*

`equipment-advisor` decides *what* to buy and *why*; `literature-review`
decides *which specific product* is good value (brand-check, source-trust,
cited summary). Don't duplicate product research here.
```

- [ ] **Step 3: Smoke test the CLI**

Run:
```bash
cd plugins/workout
python skills/equipment-advisor/scripts/advise.py --owned dumbbell --top 3
```
Expected: valid JSON with `thin_or_missing_patterns` and up to 3 `recommendations`, each with `equipment_id`, `unlocks_exercise_count`, `score`.

- [ ] **Step 4: Commit**

```bash
git add plugins/workout/skills/equipment-advisor/
git commit -m "feat(workout): add equipment-advisor skill with research-plugin handoff"
```

---

## Task 15: Full-suite verification and documentation

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: every module built in Tasks 1-14.
- Produces: nothing new -- this task verifies the whole plugin end-to-end and documents it.

- [ ] **Step 1: Run the full test suite**

Run: `cd plugins/workout && python -m pytest lib/tests -v`
Expected: all tests pass (58 tests: 7 model + 8 store + 7 exercises + 9 progression + 4 templates + 7 generator + 4 render + 6 seed + 6 advisor).

- [ ] **Step 2: Validate the plugin and marketplace manifests**

Run: `claude plugin validate plugins/workout`
Expected: validation passes with no errors.

Run: `claude plugin validate .`
Expected: validation passes with no errors (marketplace still valid with `research` and `workout` both listed).

- [ ] **Step 3: End-to-end manual smoke test**

```bash
cd plugins/workout
rm -f /tmp/workout-e2e.db
python skills/equipment-intake/scripts/intake.py --set dumbbell,pull_up_bar,sled --db /tmp/workout-e2e.db
python skills/equipment-intake/scripts/intake.py --show --db /tmp/workout-e2e.db
python skills/program-builder/scripts/build.py \
    --level beginner --days 3 --minutes 30 --equipment dumbbell,pull_up_bar,sled \
    --block-weeks 8 --format markdown --out /tmp/workout-e2e.md --db /tmp/workout-e2e.db
python skills/equipment-advisor/scripts/advise.py --owned dumbbell,pull_up_bar,sled --top 5
```
Expected: the intake profile echoes back `["dumbbell", "pull_up_bar", "sled"]`; the build step reports `Used curated template: dumbbell_beginner_3day` and writes 8 weeks of markdown; the advisor prints ranked JSON not including `dumbbell`, `pull_up_bar`, or `sled` (already owned).

Inspect the markdown by eye: `python -c "print(open('/tmp/workout-e2e.md').read())"` -- confirm it reads as a printable 8-week tracker with fill-in columns.

- [ ] **Step 4: Update CLAUDE.md**

Read the current file first -- line 7 currently reads:

```
`personal-os` is a Claude Code **plugin marketplace** (declared in `.claude-plugin/marketplace.json`) that currently hosts one plugin: `research` at `plugins/research/`. Add new plugins by dropping them under `plugins/` and appending an entry to the marketplace manifest.
```

Replace with:

```
`personal-os` is a Claude Code **plugin marketplace** (declared in `.claude-plugin/marketplace.json`) that currently hosts two plugins: `research` at `plugins/research/` and `workout` at `plugins/workout/`. Add new plugins by dropping them under `plugins/` and appending an entry to the marketplace manifest.
```

Then, directly below the existing `research` paragraph (line 9, ending `...then trust-scores and summarizes.`), insert a new paragraph:

```

The `workout` plugin (v0.1.0, 3 skills) builds progressive home-strength programs tailored to the user's equipment and physical constraints. `equipment-intake` records what gear is owned; `program-builder` picks a curated template or falls back to a pool-based generator, applies progression (variation-ladder for bodyweight, double-progression for loaded work), and renders printable markdown/CSV/JSON; `equipment-advisor` ranks equipment gaps and hands off purchase decisions to the `research` plugin's `literature-review` skill. Shared logic lives in `plugins/workout/lib/` (stdlib-only, unit-tested); a local SQLite database (outside the repo) is the system of record, seeded from git-versioned `plugins/workout/references/`.
```

In the `## Common commands` code block, after the existing `claude plugin validate plugins/research` line, add:

```
claude plugin validate plugins/workout            # plugin
```

And after the `academic-search`/`brand-check` example lines in that same block, add:

```

# Workout plugin -- run the test suite
cd plugins/workout && python -m pytest lib/tests -v

# Workout plugin pipeline: intake -> build -> advise
python plugins/workout/skills/equipment-intake/scripts/intake.py --set dumbbell,pull_up_bar
python plugins/workout/skills/program-builder/scripts/build.py --level beginner --days 3 --minutes 30 --equipment dumbbell,pull_up_bar --format markdown --out program.md
python plugins/workout/skills/equipment-advisor/scripts/advise.py --owned dumbbell,pull_up_bar
```

Finally, update the line `There are no automated tests yet — verification happens by running the scripts directly against live APIs.` to:

```
The `research` plugin has no automated tests yet -- verification happens by running the scripts directly against live APIs. The `workout` plugin's `lib/` has a full pytest suite (`cd plugins/workout && python -m pytest lib/tests -v`).
```

- [ ] **Step 5: Verify the CLAUDE.md edits render correctly**

Run: `python -c "print(open('CLAUDE.md').read()[:1200])"`
Expected: the "two plugins" sentence and the new `workout` paragraph both appear, formatted correctly.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document the workout plugin in CLAUDE.md"
```

---

## Post-plan: what's deliberately deferred

Per the design spec's scope section, the following are **not** part of this
plan and should not be added without a new spec:

- Adaptive log-and-replan loop (the `log` fields exist but stay empty)
- Android/agentic app (the SQLite schema and `lib/` API are the intended
  portable core for it, but no app code is built here)
- Cardio/conditioning, mobility, multi-goal (hypertrophy/fat-loss/endurance)
  programming
- Cloud sync of any kind
