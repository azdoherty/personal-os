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


MINUTES_TOLERANCE = 0.25


def rank_candidates(templates: list, level: str, equipment_ids, days_per_week: int) -> list:
    """Every template that qualifies for this user, best fit first.

    A template qualifies if its level and days_per_week match exactly and
    its required_equipment is fully covered by equipment_ids. Qualifying
    templates are ordered by how much of the user's gear they put to work
    (their required_equipment is by definition a subset of what's owned, so
    "requires more" means "uses more of theirs"), then alphabetically by
    template_id so the order is deterministic.

    Callers must walk this list rather than taking only the head: a template
    can qualify on equipment and still be unbuildable for this user's
    constraints (see `generator.template_buildability`), and the next
    candidate down may serve them far better than the generator fallback.
    """
    equipment_ids = set(equipment_ids)
    candidates = [
        t for t in templates
        if t["level"] == level
        and t["days_per_week"] == days_per_week
        and set(t.get("required_equipment", [])).issubset(equipment_ids)
    ]
    return sorted(
        candidates,
        key=lambda t: (-len(t.get("required_equipment", [])), t["template_id"]),
    )


def match_template(templates: list, level: str, equipment_ids, days_per_week: int):
    """The single best-fit template, or None. Thin head-of-list view of
    `rank_candidates` -- prefer that when you can fall through to a runner-up."""
    candidates = rank_candidates(templates, level, equipment_ids, days_per_week)
    return candidates[0] if candidates else None


def fits_time_budget(template: dict, requested_minutes: int) -> bool:
    """Is this template's session length compatible with the time the user has?

    A template is a fixed piece of content: its sets, reps and rest add up to
    roughly its own `session_minutes` no matter what the caller asks for. So
    a template materially *longer* than the user's budget is not a fit -- it
    would either be relabelled with a length it doesn't have, or hand someone
    with 20 minutes a 40-minute session. Being shorter than the budget is
    fine; they simply have time to spare.
    """
    return template["session_minutes"] <= requested_minutes * (1 + MINUTES_TOLERANCE)
