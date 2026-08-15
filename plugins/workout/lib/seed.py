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
