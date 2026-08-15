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
