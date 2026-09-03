# Rehab Cost Estimator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an itemized, parts+labor rehab cost estimator skill to the existing `rental` plugin, scoped to the NH Seacoast market, that prices out bathroom/kitchen/roof/electrical projects the user tells it a prospect needs.

**Architecture:** A pure-function estimation engine (`lib/rehab_cost.py`) reading a hand-tunable, individually-sourced reference file (`references/rehab-costs-nh-seacoast.json`), wrapped by one thin skill (`skills/estimate-rehab/`) that renders markdown only. Standalone — no writeback into any pipeline JSON.

**Tech Stack:** Python 3.10+ stdlib only (`json`, `re`, `dataclasses`). No new dependencies. No API calls.

## Global Constraints

- **Stdlib-only Python** — no pip dependencies in any new file.
- **Python 3.10+** — matches the rest of `plugins/rental`.
- **Markdown output only** — no JSON output from the skill script (per the approved design; this skill doesn't feed another pipeline stage).
- **Standalone skill** — does not write into `Property.rehab` or any other pipeline JSON. The user manually transcribes the total if they want it reflected in cash-on-cash.
- **NH Seacoast region-specific reference data** — hardcoded rates, no multiplier system (per the approved design's explicit tradeoff of accuracy-today over portability-to-a-future-region).
- **Every reference-file line item must have a `source` field** documenting where its figure came from, matching the convention in `plugins/research/references/domain-trust.json`.
- **Roofing and `electrical` are single-tier** (no `economy`/`luxury` split — `"tiers": null`). `bathroom_remodel` and `kitchen_remodel` are two-tier (`"tiers": ["economy", "luxury"]`).
- **The knob-and-tube removal line item auto-triggers** for `year_built < 1960`. If `year_built` is unknown, the line item is **excluded** and a warning is emitted — never silently guessed either way.
- **Cabinets are priced per linear foot (`"unit": "linear_ft"`), not per room sqft** — resolves the design spec's open item; cabinet run length drives cost, not floor area.

---

## File Structure

| File | Responsibility |
|---|---|
| `plugins/rental/references/rehab-costs-nh-seacoast.json` | Hand-tunable, sourced cost-per-unit reference data |
| `plugins/rental/lib/models.py` (modified) | Adds `LineItemCost`, `ProjectEstimate`, `RehabTotal` dataclasses |
| `plugins/rental/lib/rehab_cost.py` | Pure engine: `estimate_project`, `total_rehab_cost`, `render_markdown` |
| `plugins/rental/skills/estimate-rehab/SKILL.md` | Usage instructions for Claude |
| `plugins/rental/skills/estimate-rehab/scripts/estimate.py` | Thin CLI wrapper |
| `plugins/rental/tests/test_rehab_reference_data.py` | Schema/sanity checks on the real reference file |
| `plugins/rental/tests/test_rehab_cost.py` | Engine tests, using a small inline fixture reference dict (not the real file) |

**Script→lib bootstrap** (same pattern already used by every other skill script in this plugin):

```python
import os, sys
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)
```

---

## Task 1: Reference data file

**Files:**
- Create: `plugins/rental/references/rehab-costs-nh-seacoast.json`
- Test: `plugins/rental/tests/test_rehab_reference_data.py`

**Interfaces:**
- Produces: the reference `dict` structure every later task's `reference` parameter expects — top-level keys are project types (plus `_comment`/`_methodology` keys starting with `_`, ignored by consumers); each project type has `"tiers"` (a list of tier names, or `null`) and `"line_items"` (a list of dicts with `"name"`, `"unit"` (`"sqft"` | `"each"` | `"linear_ft"`), `"parts"`/`"labor"` (either a flat number when `"tiers"` is `null`, or a `{tier: number}` dict when tiered), optional `"trigger"` (a string like `"year_built < 1960"`), and `"source"`.

- [ ] **Step 1: Write the failing test**

`plugins/rental/tests/test_rehab_reference_data.py`:
```python
import json
import pathlib

REFERENCE_PATH = (pathlib.Path(__file__).parent.parent / "references"
                  / "rehab-costs-nh-seacoast.json")

REQUIRED_PROJECT_TYPES = {"bathroom_remodel", "kitchen_remodel", "roof_replacement", "electrical"}


def _load():
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_reference_file_is_valid_json_with_required_project_types():
    data = _load()
    keys = {k for k in data if not k.startswith("_")}
    assert REQUIRED_PROJECT_TYPES.issubset(keys)


def test_every_line_item_has_required_fields_and_matches_its_tiers_declaration():
    data = _load()
    for project_type, spec in data.items():
        if project_type.startswith("_"):
            continue
        tiers = spec.get("tiers")
        for item in spec["line_items"]:
            label = f"{project_type}/{item['name']}"
            assert item["unit"] in ("sqft", "each", "linear_ft"), label
            assert "source" in item and item["source"], label
            if tiers is None:
                assert isinstance(item["parts"], (int, float)), label
                assert isinstance(item["labor"], (int, float)), label
            else:
                assert set(item["parts"].keys()) == set(tiers), label
                assert set(item["labor"].keys()) == set(tiers), label


def test_all_rates_are_strictly_positive():
    # Strictly > 0, not >= 0: catches a leftover 0.0 placeholder that should
    # have been replaced with a real researched rate.
    data = _load()
    for project_type, spec in data.items():
        if project_type.startswith("_"):
            continue
        tiers = spec.get("tiers")
        for item in spec["line_items"]:
            label = f"{project_type}/{item['name']}"
            if tiers is None:
                assert item["parts"] > 0, label
                assert item["labor"] > 0, label
            else:
                assert all(v > 0 for v in item["parts"].values()), label
                assert all(v > 0 for v in item["labor"].values()), label


def test_knob_and_tube_line_item_has_the_expected_trigger():
    data = _load()
    kt = next(li for li in data["electrical"]["line_items"]
             if li["name"] == "Knob-and-tube removal")
    assert kt["trigger"] == "year_built < 1960"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_rehab_reference_data.py -v`
Expected: FAIL with `FileNotFoundError` (reference file doesn't exist yet).

- [ ] **Step 3: Write the reference data file**

`plugins/rental/references/rehab-costs-nh-seacoast.json`:
```json
{
  "_comment": "Rehab cost reference data for the Rochester/Dover/Somersworth/Exeter NH Seacoast corridor. Rates are $/unit, split into parts and labor. Each line item's 'source' field documents where its all-in installed-cost figure came from. Hand-tune any rate as real contractor quotes come in.",
  "_methodology": "All-in figures sourced from 2026 remodeling-cost research (national unless noted NH-specific), adjusted +10% for NH Seacoast where using national data -- derived from comparing NH Seacoast bathroom-remodel totals (~10-15% above national) and NH's explicitly-stated +15% electrical-panel-upgrade premium over national. Parts/labor split is a documented allocation, not independently sourced per item: labor-dominant trades (demo, plumbing, electrical, tile-setting) allocated ~65-80% labor; fixture/material-dominant items (cabinets, countertops, appliances, premium fixtures) allocated 60-70% parts.",
  "bathroom_remodel": {
    "tiers": ["economy", "luxury"],
    "line_items": [
      {"name": "Demo & prep", "unit": "sqft",
       "parts": {"economy": 2.0, "luxury": 3.0}, "labor": {"economy": 10.0, "luxury": 15.0},
       "source": "Nat'l demo labor $500-1,500/project (This Old House 2026), NH +10%, ~80% labor"},
      {"name": "Plumbing rough-in", "unit": "sqft",
       "parts": {"economy": 6.0, "luxury": 12.0}, "labor": {"economy": 16.0, "luxury": 26.0},
       "source": "Nat'l plumbing labor $1,000-4,000/project (This Old House 2026), NH +10%, ~35% parts"},
      {"name": "Electrical (GFCI, fan wiring)", "unit": "sqft",
       "parts": {"economy": 3.0, "luxury": 6.0}, "labor": {"economy": 7.0, "luxury": 12.0},
       "source": "Nat'l electrical labor $500-2,000/project (This Old House 2026), NH +10%, ~35% parts"},
      {"name": "Tile - floor", "unit": "sqft",
       "parts": {"economy": 3.0, "luxury": 10.0}, "labor": {"economy": 7.0, "luxury": 12.0},
       "source": "Nat'l tile labor $1,000-3,000/project + material $2-15/sqft (This Old House 2026), NH +10%"},
      {"name": "Tile - tub/shower surround", "unit": "sqft",
       "parts": {"economy": 4.0, "luxury": 12.0}, "labor": {"economy": 9.0, "luxury": 15.0},
       "source": "Same basis as floor tile, wet-wall labor premium for waterproofing, NH +10%"},
      {"name": "Toilet", "unit": "each",
       "parts": {"economy": 150.0, "luxury": 700.0}, "labor": {"economy": 150.0, "luxury": 250.0},
       "source": "Installed $200-800 budget-mid, $800+ luxury (Angi 2026), NH +10%"},
      {"name": "Vanity + sink", "unit": "each",
       "parts": {"economy": 350.0, "luxury": 2500.0}, "labor": {"economy": 200.0, "luxury": 400.0},
       "source": "Installed $400-5,000, standard avg ~$1,600, custom ~$4,000+ (Angi/DIY Depot 2026), NH +10%"},
      {"name": "Tub/shower unit", "unit": "each",
       "parts": {"economy": 700.0, "luxury": 4500.0}, "labor": {"economy": 500.0, "luxury": 1200.0},
       "source": "Bathtub $1,100-5,900, shower $600 prefab to $10,000+ custom (HomeLight/Angi 2026), NH +10%"},
      {"name": "Paint/drywall", "unit": "sqft",
       "parts": {"economy": 0.6, "luxury": 1.0}, "labor": {"economy": 1.2, "luxury": 1.8},
       "source": "Nat'l finish-carpentry labor $500-1,500/project allocated to paint/drywall scope, NH +10%"}
    ]
  },
  "kitchen_remodel": {
    "tiers": ["economy", "luxury"],
    "line_items": [
      {"name": "Demo & prep", "unit": "sqft",
       "parts": {"economy": 3.0, "luxury": 5.0}, "labor": {"economy": 5.0, "luxury": 9.0},
       "source": "Scaled up from bathroom demo (more built-ins to remove), NH +10%"},
      {"name": "Cabinets", "unit": "linear_ft",
       "parts": {"economy": 70.0, "luxury": 850.0}, "labor": {"economy": 30.0, "luxury": 150.0},
       "source": "Stock $100-300/linear ft, custom $500-1,200+/linear ft, luxury $1,500+/linear ft (HomeAdvisor/NextDayCabinets 2026), NH +10%. Priced per linear foot of cabinet run, not room sqft -- run length drives cost."},
      {"name": "Countertops", "unit": "sqft",
       "parts": {"economy": 20.0, "luxury": 75.0}, "labor": {"economy": 10.0, "luxury": 20.0},
       "source": "Laminate $25-40/sqft, quartz/granite $50-175/sqft, nat'l avg $75-95/sqft (SlabWise/Homewyse 2026), NH +10%"},
      {"name": "Appliance package", "unit": "each",
       "parts": {"economy": 3500.0, "luxury": 55000.0}, "labor": {"economy": 500.0, "luxury": 2000.0},
       "source": "Standard package (fridge/microwave/range/dishwasher) $2,100-5,400; luxury $45,000-90,000+ (Yale Appliance/HomeGuide 2026), NH +10%. Flat per-kitchen line, not sqft-scaled -- dominates the luxury-tier total, flag prominently in output."},
      {"name": "Kitchen plumbing (sink, dishwasher, disposal)", "unit": "each",
       "parts": {"economy": 300.0, "luxury": 900.0}, "labor": {"economy": 400.0, "luxury": 700.0},
       "source": "Derived from bathroom plumbing-per-fixture basis, NH +10%"},
      {"name": "Kitchen electrical (circuits, under-cabinet lighting)", "unit": "each",
       "parts": {"economy": 250.0, "luxury": 800.0}, "labor": {"economy": 550.0, "luxury": 1200.0},
       "source": "Derived from bathroom electrical basis, scaled for kitchen's higher circuit-count code requirements, NH +10%"},
      {"name": "Flooring", "unit": "sqft",
       "parts": {"economy": 3.0, "luxury": 9.0}, "labor": {"economy": 3.0, "luxury": 6.0},
       "source": "LVP/laminate $2-5/sqft materials, hardwood/tile $6-12/sqft materials (general market pricing), NH +10%"},
      {"name": "Backsplash", "unit": "sqft",
       "parts": {"economy": 6.0, "luxury": 20.0}, "labor": {"economy": 8.0, "luxury": 12.0},
       "source": "Subway-tile economy to natural-stone/glass luxury, same basis as bathroom tile, NH +10%"}
    ]
  },
  "roof_replacement": {
    "tiers": null,
    "line_items": [
      {"name": "Tear-off, underlayment, shingle, flashing", "unit": "sqft",
       "parts": 2.5, "labor": 4.5,
       "source": "$5.50-8.50/sqft installed, NH-specific -- already localized for snow-load/ice-dam installation requirements (RoofVista/Compass Exteriors 2026), no further regional adjustment applied. Single tier: asphalt shingle is standard for rental properties; a metal/slate luxury tier was considered and rejected as not useful for rental-investment decisions."}
    ]
  },
  "electrical": {
    "tiers": null,
    "line_items": [
      {"name": "Panel upgrade (200A)", "unit": "each",
       "parts": 1200.0, "labor": 2300.0,
       "source": "$1,725-5,175 in NH, explicitly +15% above national average (CostOnce/TMB Electric Corp 2026), NH-specific, no further adjustment applied"},
      {"name": "General rewire", "unit": "sqft",
       "parts": 3.0, "labor": 5.0,
       "source": "$6-10/sqft nationally (This Old House 2026); NH electrical panel data confirms NH runs above national, and this range's midpoint already sits within that premium -- no further multiplier applied to avoid compounding two separate regional adjustments"},
      {"name": "Knob-and-tube removal", "unit": "sqft", "trigger": "year_built < 1960",
       "parts": 4.0, "labor": 8.0,
       "source": "$10,000-30,000 additional for pre-1960 knob-and-tube homes nationally (CostOnce/TMB Electric Corp 2026), backed out to $/sqft for a typical 1,800-2,500 sqft multi-family building. Additive on top of General rewire, not a replacement for it."}
    ]
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/rental && python -m pytest tests/test_rehab_reference_data.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/rental/references/rehab-costs-nh-seacoast.json plugins/rental/tests/test_rehab_reference_data.py
git commit -m "feat(rental): add NH Seacoast rehab cost reference data"
```

---

## Task 2: Data models + `estimate_project`

**Files:**
- Modify: `plugins/rental/lib/models.py` (append new dataclasses at the end of the file)
- Create: `plugins/rental/lib/rehab_cost.py`
- Create: `plugins/rental/tests/test_rehab_cost.py`

**Interfaces:**
- Consumes: nothing new from other tasks (uses the reference `dict` shape from Task 1, but tests use an inline fixture, not the real file — per the design's explicit choice to keep engine tests independent of hand-tuned real numbers).
- Produces:
  - `@dataclass LineItemCost(name: str, unit: str, quantity: float, parts_rate: float, labor_rate: float, parts_subtotal: float, labor_subtotal: float, subtotal: float)` in `lib/models.py`.
  - `@dataclass ProjectEstimate(project_type: str, tier: str | None, line_items: list[LineItemCost], parts_total: float, labor_total: float, total: float, warnings: list[str] = field(default_factory=list))` in `lib/models.py`.
  - `@dataclass RehabTotal(projects: list[ProjectEstimate], grand_total: float)` in `lib/models.py`.
  - `class UnknownProjectTypeError(Exception)` and `class TierError(Exception)` in `lib/rehab_cost.py`.
  - `estimate_project(project_type: str, sqft: float, reference: dict, tier: str | None = None, fixture_counts: dict[str, int] | None = None, year_built: int | None = None) -> ProjectEstimate` in `lib/rehab_cost.py`.

- [ ] **Step 1: Write the failing test**

`plugins/rental/tests/test_rehab_cost.py`:
```python
import pytest
from lib.rehab_cost import estimate_project, UnknownProjectTypeError, TierError

TEST_REFERENCE = {
    "bathroom_remodel": {
        "tiers": ["economy", "luxury"],
        "line_items": [
            {"name": "Tile - floor", "unit": "sqft",
             "parts": {"economy": 3.0, "luxury": 10.0},
             "labor": {"economy": 7.0, "luxury": 12.0}},
            {"name": "Toilet", "unit": "each",
             "parts": {"economy": 150.0, "luxury": 700.0},
             "labor": {"economy": 150.0, "luxury": 250.0}},
        ],
    },
    "roof_replacement": {
        "tiers": None,
        "line_items": [
            {"name": "Tear-off, underlayment, shingle, flashing", "unit": "sqft",
             "parts": 2.5, "labor": 4.5},
        ],
    },
    "electrical": {
        "tiers": None,
        "line_items": [
            {"name": "General rewire", "unit": "sqft", "parts": 3.0, "labor": 5.0},
            {"name": "Knob-and-tube removal", "unit": "sqft", "parts": 4.0, "labor": 8.0,
             "trigger": "year_built < 1960"},
        ],
    },
}


def test_sqft_line_item_computed_correctly_single_tier():
    est = estimate_project("roof_replacement", sqft=1450, reference=TEST_REFERENCE)
    assert est.parts_total == pytest.approx(1450 * 2.5)
    assert est.labor_total == pytest.approx(1450 * 4.5)
    assert est.total == pytest.approx(1450 * 7.0)
    assert len(est.line_items) == 1
    assert est.line_items[0].quantity == 1450


def test_each_line_item_with_fixture_count_override():
    est = estimate_project("bathroom_remodel", sqft=50, tier="economy",
                           fixture_counts={"Toilet": 2}, reference=TEST_REFERENCE)
    toilet = next(li for li in est.line_items if li.name == "Toilet")
    assert toilet.quantity == 2
    assert toilet.subtotal == pytest.approx(2 * (150.0 + 150.0))


def test_each_line_item_defaults_to_one_fixture():
    est = estimate_project("bathroom_remodel", sqft=50, tier="luxury",
                           reference=TEST_REFERENCE)
    toilet = next(li for li in est.line_items if li.name == "Toilet")
    assert toilet.quantity == 1
    assert toilet.subtotal == pytest.approx(700.0 + 250.0)


def test_knob_and_tube_included_for_pre_1960_property():
    est = estimate_project("electrical", sqft=2000, year_built=1902,
                           reference=TEST_REFERENCE)
    names = [li.name for li in est.line_items]
    assert "Knob-and-tube removal" in names
    kt = next(li for li in est.line_items if li.name == "Knob-and-tube removal")
    assert kt.subtotal == pytest.approx(2000 * (4.0 + 8.0))
    assert est.warnings == []


def test_knob_and_tube_excluded_for_post_1960_property():
    est = estimate_project("electrical", sqft=2000, year_built=1975,
                           reference=TEST_REFERENCE)
    names = [li.name for li in est.line_items]
    assert "Knob-and-tube removal" not in names
    assert est.warnings == []


def test_knob_and_tube_excluded_with_warning_when_year_built_unknown():
    est = estimate_project("electrical", sqft=2000, year_built=None,
                           reference=TEST_REFERENCE)
    names = [li.name for li in est.line_items]
    assert "Knob-and-tube removal" not in names
    assert len(est.warnings) == 1
    assert "year_built unknown" in est.warnings[0]


def test_unknown_project_type_raises_with_valid_types_listed():
    with pytest.raises(UnknownProjectTypeError) as e:
        estimate_project("swimming_pool", sqft=100, reference=TEST_REFERENCE)
    assert "bathroom_remodel" in str(e.value)


def test_tier_required_but_missing_raises():
    with pytest.raises(TierError):
        estimate_project("bathroom_remodel", sqft=50, reference=TEST_REFERENCE)


def test_tier_supplied_but_not_allowed_raises():
    with pytest.raises(TierError):
        estimate_project("roof_replacement", sqft=1450, tier="economy",
                         reference=TEST_REFERENCE)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_rehab_cost.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.rehab_cost'`.

- [ ] **Step 3: Add the dataclasses to `lib/models.py`**

Append to the end of `plugins/rental/lib/models.py` (the file already imports `dataclass` and `field` from `dataclasses` — no new imports needed):
```python
@dataclass
class LineItemCost:
    name: str
    unit: str
    quantity: float
    parts_rate: float
    labor_rate: float
    parts_subtotal: float
    labor_subtotal: float
    subtotal: float


@dataclass
class ProjectEstimate:
    project_type: str
    tier: str | None
    line_items: list[LineItemCost]
    parts_total: float
    labor_total: float
    total: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class RehabTotal:
    projects: list[ProjectEstimate]
    grand_total: float
```

- [ ] **Step 4: Write `lib/rehab_cost.py`**

`plugins/rental/lib/rehab_cost.py`:
```python
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
```

Note: for `"linear_ft"`-unit line items (cabinets), the caller passes the cabinet run length as the `sqft` parameter — there's a single scalar "size" input per project, reused for whichever unit the project type's sqft-like line items declare. This keeps the function signature simple (one size parameter, not one per possible unit) since no project type mixes `sqft` and `linear_ft` line items together.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd plugins/rental && python -m pytest tests/test_rehab_cost.py -v`
Expected: PASS (9 passed).

- [ ] **Step 6: Commit**

```bash
git add plugins/rental/lib/models.py plugins/rental/lib/rehab_cost.py plugins/rental/tests/test_rehab_cost.py
git commit -m "feat(rental): add rehab cost models and estimate_project engine"
```

---

## Task 3: `total_rehab_cost` + `render_markdown`

**Files:**
- Modify: `plugins/rental/lib/rehab_cost.py`
- Modify: `plugins/rental/tests/test_rehab_cost.py`

**Interfaces:**
- Consumes: `estimate_project`, `TEST_REFERENCE`, `RehabTotal` (Task 2).
- Produces:
  - `total_rehab_cost(estimates: list) -> RehabTotal` in `lib/rehab_cost.py`.
  - `render_markdown(total) -> str` in `lib/rehab_cost.py`.

- [ ] **Step 1: Write the failing test**

Append to `plugins/rental/tests/test_rehab_cost.py`:
```python
from lib.rehab_cost import total_rehab_cost, render_markdown


def test_total_rehab_cost_sums_multiple_projects():
    roof = estimate_project("roof_replacement", sqft=1450, reference=TEST_REFERENCE)
    bath = estimate_project("bathroom_remodel", sqft=50, tier="economy",
                            reference=TEST_REFERENCE)
    result = total_rehab_cost([roof, bath])
    assert result.grand_total == pytest.approx(roof.total + bath.total)
    assert len(result.projects) == 2


def test_total_rehab_cost_empty_list():
    result = total_rehab_cost([])
    assert result.grand_total == 0.0
    assert result.projects == []


def test_render_markdown_includes_line_items_and_grand_total():
    roof = estimate_project("roof_replacement", sqft=1450, reference=TEST_REFERENCE)
    result = total_rehab_cost([roof])
    md = render_markdown(result)
    assert "Roof Replacement" in md
    assert "Tear-off, underlayment, shingle, flashing" in md
    assert f"${roof.total:,.2f}" in md
    assert f"${result.grand_total:,.2f}" in md


def test_render_markdown_surfaces_warnings():
    est = estimate_project("electrical", sqft=2000, year_built=None, reference=TEST_REFERENCE)
    result = total_rehab_cost([est])
    md = render_markdown(result)
    assert "year_built unknown" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_rehab_cost.py -v`
Expected: FAIL with `ImportError: cannot import name 'total_rehab_cost'`.

- [ ] **Step 3: Add the functions to `lib/rehab_cost.py`**

Append to `plugins/rental/lib/rehab_cost.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/rental && python -m pytest tests/test_rehab_cost.py -v`
Expected: PASS (13 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/rental/lib/rehab_cost.py plugins/rental/tests/test_rehab_cost.py
git commit -m "feat(rental): add total_rehab_cost summing and markdown rendering"
```

---

## Task 4: `estimate-rehab` skill

**Files:**
- Create: `plugins/rental/skills/estimate-rehab/SKILL.md`
- Create: `plugins/rental/skills/estimate-rehab/scripts/estimate.py`

**Interfaces:**
- Consumes: `estimate_project`, `total_rehab_cost`, `render_markdown`, `UnknownProjectTypeError`, `TierError` (Tasks 2-3); the real reference file (Task 1).
- Produces: CLI `estimate.py` reading a JSON project-spec list on stdin, printing markdown to stdout.

- [ ] **Step 1: Write the script**

`plugins/rental/skills/estimate-rehab/scripts/estimate.py`:
```python
#!/usr/bin/env python3
"""Read a JSON list of rehab project specs on stdin, compute itemized cost
estimates using the NH Seacoast reference data, and print a markdown report.

Each project spec: {"project_type": str, "sqft": float, "tier": str|omit,
"fixture_counts": dict|omit, "year_built": int|omit}.
"""
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from lib.rehab_cost import (
    estimate_project, total_rehab_cost, render_markdown,
    UnknownProjectTypeError, TierError,
)

REFERENCE_PATH = os.path.join(_PLUGIN_ROOT, "references", "rehab-costs-nh-seacoast.json")


def main() -> int:
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)

    specs = json.load(sys.stdin)
    estimates = []
    for spec in specs:
        try:
            estimates.append(estimate_project(
                project_type=spec["project_type"],
                sqft=spec["sqft"],
                reference=reference,
                tier=spec.get("tier"),
                fixture_counts=spec.get("fixture_counts"),
                year_built=spec.get("year_built"),
            ))
        except (UnknownProjectTypeError, TierError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    result = total_rehab_cost(estimates)
    print(render_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note the `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` guard, carried forward from a real bug found earlier in this plugin (`skills/report/scripts/report.py`): without it, the `⚠️` warning-emoji character in `render_markdown`'s output crashes on a Windows console using a non-UTF-8 codepage.

- [ ] **Step 2: Verify the script end-to-end**

Run (adjust `python`/`python3`/`py` to whatever resolves in this environment):
```bash
cd plugins/rental
echo '[{"project_type": "roof_replacement", "sqft": 1450}]' | python skills/estimate-rehab/scripts/estimate.py
```
Expected: markdown prints to stdout with a "Roof Replacement" section, a line item row, a project total, and a "Grand total" line. No traceback.

Also verify the error path:
```bash
echo '[{"project_type": "swimming_pool", "sqft": 100}]' | python skills/estimate-rehab/scripts/estimate.py; echo "exit=$?"
```
Expected: stderr shows `error: Unknown project_type ...`, `exit=2`.

- [ ] **Step 3: Write the SKILL.md**

`plugins/rental/skills/estimate-rehab/SKILL.md`:
````markdown
---
name: estimate-rehab
version: 0.1.0
description: Itemized parts+labor rehab cost estimate for a rental prospect, scoped to the NH Seacoast market (Rochester/Dover/Somersworth/Exeter corridor). Covers bathroom remodel, kitchen remodel, roof replacement, and electrical (panel upgrade, rewire, and an auto-triggered knob-and-tube line item for pre-1960 properties). Use when the user wants to know what a property's needed work would cost, e.g. "estimate rehab for X" or "how much would it cost to redo the bathroom/kitchen/roof/electrical at X". Renders a markdown breakdown -- does not modify any pipeline JSON or the rehab field.
allowed-tools:
  - Bash
---

# estimate-rehab

Itemized rehab cost estimator for the NH Seacoast market. You tell it what work a
property needs (from photos, a walkthrough, or agent notes -- the tool does not infer
condition); it prices it out per line item with separate parts and labor costs.

## When to use

- The user has a rental prospect they suspect needs work and wants a cost estimate.
- Covers: `bathroom_remodel`, `kitchen_remodel`, `roof_replacement`, `electrical`.

## How to invoke

Build a JSON array of project specs and pipe it to the script:

```bash
echo '[
  {"project_type": "bathroom_remodel", "sqft": 60, "tier": "economy"},
  {"project_type": "electrical", "sqft": 4358, "year_built": 1902}
]' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/estimate-rehab/scripts/estimate.py
```

Each project spec:
- `project_type` (required): one of `bathroom_remodel`, `kitchen_remodel` (both require
  `tier`), `roof_replacement`, `electrical` (neither takes `tier`).
- `sqft` (required): the room's or building's relevant square footage. For
  `kitchen_remodel`'s `Cabinets` line item this is actually cabinet run length in linear
  feet, not room floor area -- pass the linear-foot number as `sqft` for that project.
- `tier` (required for bathroom/kitchen, omit for roof/electrical): `"economy"` or
  `"luxury"`.
- `fixture_counts` (optional): `{"Toilet": 2}` to override the default count of 1 for an
  `each`-unit line item. Line item names must match the reference file exactly (see
  `references/rehab-costs-nh-seacoast.json`).
- `year_built` (optional but recommended for `electrical`): triggers the knob-and-tube
  removal line item for properties built before 1960. If omitted, that cost is excluded
  and the output carries an explicit warning rather than guessing.

## Output

Markdown only: a table per project (line item, quantity, parts rate, labor rate,
subtotal), each project's total, and a grand total across every project specified. Any
warnings (e.g. unknown `year_built`) are called out inline, not buried.

## Gathering project specs from the conversation

When the user describes what a property needs in prose ("the bathroom needs a full redo,
economy grade, roof looks original"), translate that into the JSON array above -- ask for
missing `sqft`/`tier` values rather than guessing them, and pass the property's
`year_built` (already available from the rental pipeline's ingest step, if you have it)
for `electrical` projects so the knob-and-tube check fires correctly.

## Not included

- Contractor discovery/quotes -- a separate skill, not built yet.
- Writing the total back into a property's `rehab` field for cash-on-cash -- standalone
  by design; re-run `/report` manually with the number if you want it reflected.
- Condition assessment -- you tell it what's needed; it doesn't infer condition from
  photos or listing text.
````

- [ ] **Step 4: Commit**

```bash
git add plugins/rental/skills/estimate-rehab
git commit -m "feat(rental): add estimate-rehab skill"
```

---

## Task 5: Final validation + docs

**Files:**
- Modify: `CLAUDE.md` (repo root)
- Modify: `plugins/rental/.claude-plugin/plugin.json`

**Interfaces:** none (docs + validation only).

- [ ] **Step 1: Run the full plugin test suite**

Run: `cd plugins/rental && python -m pytest -v`
Expected: all tests pass (38 pre-existing + 4 from Task 1 + 13 from Tasks 2-3 = 55 total; exact count may vary slightly, but there must be zero failures and pristine output).

- [ ] **Step 2: Attempt manifest validation**

Run: `claude plugin validate plugins/rental && claude plugin validate .`
If the `claude` CLI isn't on PATH in this shell (a known limitation encountered earlier
in this plugin's development), note that clearly rather than treating it as a task
failure -- it should be run once in an interactive Claude Code session before merge.

- [ ] **Step 3: Bump the plugin version**

In `plugins/rental/.claude-plugin/plugin.json`, change `"version": "0.1.0"` to
`"version": "0.2.0"` (a new skill was added) and update the `"description"` field to
mention rehab cost estimation, e.g. append: `" Also estimates itemized rehab costs
(bathroom/kitchen/roof/electrical) for the NH Seacoast market."`

- [ ] **Step 4: Update root CLAUDE.md**

In `CLAUDE.md` at the repo root, find the sentence describing the `rental` plugin (starts
with `` The `rental` plugin (v0.1.0, 6 skills) analyzes local 2-4 unit... ``) and update
it to `` The `rental` plugin (v0.2.0, 7 skills) analyzes local 2-4 unit multifamily
listings for long-term rental investment ... It also estimates itemized rehab costs
(bathroom/kitchen/roof/electrical, parts+labor, NH Seacoast-specific) via
`estimate-rehab`. `` -- adjust wording to flow naturally with whatever the sentence's
current exact text is (read the file first; it may have been edited since this plan was
written).

- [ ] **Step 5: End-to-end smoke test with realistic numbers**

Run (adjust `python`/`python3`/`py` as needed):
```bash
cd plugins/rental
echo '[
  {"project_type": "bathroom_remodel", "sqft": 60, "tier": "economy"},
  {"project_type": "electrical", "sqft": 4358, "year_built": 1902}
]' | python skills/estimate-rehab/scripts/estimate.py
```
Expected: markdown with two project sections (`Bathroom Remodel (economy)` and
`Electrical`), the electrical section including a `Knob-and-tube removal` row (since
1902 < 1960) with no warning, and a grand total in the neighborhood of $90,000-$95,000
(bathroom ~$6,200 + electrical ~$87,000 for a 4,358 sqft century-old building's full
rewire-plus-knob-and-tube-removal -- a large number, and a genuinely useful signal that
this specific property's electrical scope is a major cost driver, not a bug in the
estimate). No traceback.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md plugins/rental/.claude-plugin/plugin.json
git commit -m "docs(rental): document estimate-rehab skill, bump plugin to 0.2.0"
```

---

## Self-Review

**1. Spec coverage:**
- Pure engine, no I/O → Task 2/3 (`lib/rehab_cost.py` has no file/network access). ✓
- Hand-tunable, sourced reference file, NH Seacoast-specific, no multiplier → Task 1. ✓
- `sqft`/`each` units, tiers (bathroom/kitchen) vs. single-tier (roof/electrical) → Task 2. ✓
- Knob-and-tube auto-trigger on `year_built < 1960`, excluded+warned when unknown → Task 2, tested three ways (pre-1960, post-1960, unknown). ✓
- `total_rehab_cost` multi-project summing → Task 3. ✓
- Markdown-only output, no JSON → Task 3 (`render_markdown`) + Task 4 (script prints markdown, nothing else). ✓
- Standalone skill, no pipeline writeback → Task 4's script has no code path that touches `Property.rehab` or any other file; SKILL.md explicitly documents this under "Not included". ✓
- Cabinets priced per linear foot, not sqft → resolved in Task 1's reference data and documented in Task 4's SKILL.md. ✓
- Every line item has a `source` → Task 1, enforced by a test. ✓
- Contractor-finding out of scope → not built, explicitly noted in SKILL.md. ✓

**2. Placeholder scan:** No "TBD"/"TODO" in any task's code or reference data -- Task 1's
reference file contains real, individually-sourced dollar figures (not backed out of
blended totals), each with a `source` string, per the design's explicit requirement and
the writing-plans "No Placeholders" rule. The strictly-positive-rate test in Task 1
guards against a leftover `0.0` ever slipping through un-researched.

**3. Type consistency:** `estimate_project`'s signature (`project_type, sqft, reference,
tier, fixture_counts, year_built`) is used identically in Task 2's tests, Task 3's tests,
and Task 4's script. `ProjectEstimate`/`LineItemCost`/`RehabTotal` field names match
between their Task 2 definition and every consumer (`total_rehab_cost`, `render_markdown`
in Task 3; nothing in Task 4 touches their fields directly, only passes objects through).
`UnknownProjectTypeError`/`TierError` are defined once in Task 2 and imported identically
in Task 4.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-25-rehab-cost-estimator.md`.

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
