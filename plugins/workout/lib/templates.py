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
