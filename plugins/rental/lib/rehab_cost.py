"""Pure rehab cost estimation engine. No I/O, no network.

Line items are either "sqft"/"linear_ft"-scaled (quantity = the project's
square footage or cabinet run length) or "each"-scaled (quantity = a fixture
count, default 1 per fixture type). A line item's "trigger" (currently only
"year_built < N", used for the knob-and-tube removal line item) is evaluated
against the property's year_built; if year_built is unknown, the line item is
excluded and a warning is emitted rather than guessing either way.
"""
from __future__ import annotations

import re

from lib.models import LineItemCost, ProjectEstimate, RehabTotal


class UnknownProjectTypeError(Exception):
    pass


class TierError(Exception):
    pass


def _evaluate_trigger(trigger: str, year_built: int | None) -> tuple[bool, str | None]:
    """Returns (include, warning). Currently only supports 'year_built < N'."""
    match = re.match(r"year_built\s*<\s*(\d+)", trigger)
    if not match:
        return True, None
    threshold = int(match.group(1))
    if year_built is None:
        return False, (
            f"year_built unknown -- a cost that only applies when year_built < "
            f"{threshold} was NOT included; verify manually if the property is that old."
        )
    return year_built < threshold, None


def estimate_project(project_type: str, sqft: float, reference: dict,
                     tier: str | None = None,
                     fixture_counts: dict[str, int] | None = None,
                     year_built: int | None = None) -> ProjectEstimate:
    if project_type not in reference:
        valid = ", ".join(sorted(k for k in reference if not k.startswith("_")))
        raise UnknownProjectTypeError(
            f"Unknown project_type {project_type!r}. Valid types: {valid}."
        )
    spec = reference[project_type]
    tiers = spec.get("tiers")
    if tiers is None and tier is not None:
        raise TierError(f"{project_type!r} has no quality tiers; omit tier.")
    if tiers is not None and tier not in tiers:
        raise TierError(
            f"{project_type!r} requires tier to be one of {tiers}, got {tier!r}."
        )

    fixture_counts = fixture_counts or {}
    line_items: list[LineItemCost] = []
    warnings: list[str] = []

    for item in spec["line_items"]:
        trigger = item.get("trigger")
        if trigger:
            include, warning = _evaluate_trigger(trigger, year_built)
            if warning:
                warnings.append(warning)
            if not include:
                continue

        if tiers is not None:
            parts_rate = item["parts"][tier]
            labor_rate = item["labor"][tier]
        else:
            parts_rate = item["parts"]
            labor_rate = item["labor"]

        if item["unit"] in ("sqft", "linear_ft"):
            quantity = sqft
        elif item["unit"] == "each":
            quantity = fixture_counts.get(item["name"], 1)
        else:
            raise ValueError(f"Unknown unit {item['unit']!r} on line item {item['name']!r}.")

        parts_subtotal = parts_rate * quantity
        labor_subtotal = labor_rate * quantity
        line_items.append(LineItemCost(
            name=item["name"], unit=item["unit"], quantity=quantity,
            parts_rate=parts_rate, labor_rate=labor_rate,
            parts_subtotal=parts_subtotal, labor_subtotal=labor_subtotal,
            subtotal=parts_subtotal + labor_subtotal,
        ))

    parts_total = sum(li.parts_subtotal for li in line_items)
    labor_total = sum(li.labor_subtotal for li in line_items)
    return ProjectEstimate(
        project_type=project_type, tier=tier, line_items=line_items,
        parts_total=parts_total, labor_total=labor_total,
        total=parts_total + labor_total, warnings=warnings,
    )


def total_rehab_cost(estimates: list[ProjectEstimate]) -> RehabTotal:
    return RehabTotal(projects=estimates, grand_total=sum(e.total for e in estimates))


def render_markdown(total: RehabTotal) -> str:
    lines = ["# Rehab cost estimate", ""]
    for est in total.projects:
        tier_label = f" ({est.tier})" if est.tier else ""
        lines.append(f"## {est.project_type.replace('_', ' ').title()}{tier_label}")
        lines.append("")
        lines.append("| Line item | Qty | Parts rate | Labor rate | Subtotal |")
        lines.append("|---|---|---|---|---|")
        for li in est.line_items:
            lines.append(
                f"| {li.name} | {li.quantity:,.1f} {li.unit} | ${li.parts_rate:,.2f} "
                f"| ${li.labor_rate:,.2f} | ${li.subtotal:,.2f} |"
            )
        lines.append("")
        lines.append(f"**Project total: ${est.total:,.2f}** "
                     f"(parts ${est.parts_total:,.2f} + labor ${est.labor_total:,.2f})")
        for warning in est.warnings:
            lines.append(f"> ⚠️ {warning}")
        lines.append("")
    lines.append(f"## Grand total: ${total.grand_total:,.2f}")
    return "\n".join(lines)
