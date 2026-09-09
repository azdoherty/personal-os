# Design: rehab cost estimator (`rental` plugin extension)

**Date:** 2026-08-25
**Status:** Approved (brainstorming), pending implementation plan
**Marketplace:** `personal-os`, `rental` plugin

## Goal

Given a rental prospect that needs work — e.g. 352 Portland St, Rochester NH, a triplex
flagged by the existing screening pipeline as the strongest cash-on-cash candidate but
suspected to need renovation — produce an itemized, parts-and-labor rehab cost estimate
per project (bathroom, kitchen, roof, electrical), at a chosen quality tier, scaled by
square footage or fixture count. The user manually decides what work a property needs
(from photos, a walkthrough, agent notes); this tool prices out that decision.

This is scoped to **rental prospects only** — an extension of the `rental` plugin, not a
general-purpose home-improvement estimator. It is a **standalone skill**: it does not
write back into a property's `rehab` field or any other pipeline JSON. The user manually
transcribes the total into a re-run of `report` if they want it reflected in cash-on-cash.

**Explicitly out of scope:** finding local contractors. That's a second, separate skill,
designed after this one ships — a local-business-search problem (closer to the `research`
plugin's `brand-check` pattern) rather than a cost-modeling problem.

## Why square-footage-driven, itemized, parts+labor

The user's own framing: "every estimate is driven by a parts list and a labor list... we
estimate the cost based on the square footage and the line items in it, such as plumbing
versus tiling versus other operations." This rules out a single ballpark-total heuristic
(too coarse to act on) and rules out automated condition detection (the user decides what
needs work, not the tool). Parts and labor are tracked as separate columns per line item
— useful for comparing against real contractor quotes later, and for partial-DIY planning
(buy materials, hire out labor, or vice versa).

## Regional pricing: NH Seacoast-specific, not national + multiplier

Renovation costs are hyperlocal — confirmed via research: NH Seacoast bathroom/kitchen
remodel costs run meaningfully above national averages, and NH roofing costs specifically
run higher than the national average due to snow-load/ice-dam installation requirements.
Two designs were considered: a national baseline with a regional multiplier (the RSMeans/
industry-standard approach, portable to new regions cheaply), versus region-specific rates
researched directly. The user chose the latter: **since the user's actual search is
concentrated in the Rochester/Dover/Somersworth/Exeter NH corridor, rates are researched
and hardcoded directly for that region**, prioritizing accuracy today over portability to
a hypothetical future region. If prospects in a different region (e.g. Boston metro) ever
enter the pipeline, that would mean a second, parallel reference file rather than a
multiplier on this one — an explicit, accepted tradeoff.

## Architecture

New files inside the existing `plugins/rental/` plugin, following its established
conventions (a pure, unit-tested `lib/` core + a documented, hand-tunable reference file +
a thin skill wrapper — the same shape as `underwrite.py`/`expense-defaults.json`):

```
plugins/rental/
  lib/
    rehab_cost.py                        # pure estimation engine, no I/O
  references/
    rehab-costs-nh-seacoast.json         # region-named; a second region gets its own file
  skills/
    estimate-rehab/
      SKILL.md
      scripts/estimate.py                # thin wrapper: reads project list JSON, renders markdown
  tests/
    test_rehab_cost.py
```

## Reference data schema

Each **project type** defines a list of **line items**. Each line item has a `unit` —
`"sqft"` (cost scales with the project's square footage) or `"each"` (a flat cost per
countable fixture, e.g. a toilet or an electrical panel) — and, for tiered project types,
separate `parts` and `labor` rates per quality tier:

```jsonc
{
  "_comment": "NH Seacoast (Rochester/Dover/Somersworth/Exeter corridor) rehab cost "
              "reference. Each line item documents its source and research date, "
              "the same way plugins/research/references/domain-trust.json documents "
              "its trust tiers. Hand-tune any rate as real contractor quotes come in.",
  "bathroom_remodel": {
    "tiers": ["economy", "luxury"],
    "line_items": [
      {"name": "Demo & prep", "unit": "sqft",
       "parts": {"economy": 0.0, "luxury": 0.0}, "labor": {"economy": 0.0, "luxury": 0.0},
       "source": "TBD during implementation"},
      {"name": "Toilet", "unit": "each",
       "parts": {"economy": 0.0, "luxury": 0.0}, "labor": {"economy": 0.0, "luxury": 0.0},
       "source": "TBD during implementation"}
    ]
  },
  "kitchen_remodel": {"tiers": ["economy", "luxury"], "line_items": ["..."]},
  "roof_replacement": {
    "tiers": null,
    "line_items": [
      {"name": "Tear-off, underlayment, asphalt shingle, flashing", "unit": "sqft",
       "parts": 0.0, "labor": 0.0, "source": "TBD during implementation"}
    ]
  },
  "electrical": {
    "tiers": null,
    "line_items": [
      {"name": "Panel upgrade (200A)", "unit": "each", "parts": 0.0, "labor": 0.0},
      {"name": "General rewire", "unit": "sqft", "parts": 0.0, "labor": 0.0},
      {"name": "Knob-and-tube removal (pre-1960 only)", "unit": "sqft",
       "parts": 0.0, "labor": 0.0, "trigger": "year_built < 1960"}
    ]
  }
}
```

**Explicit values in this design doc are placeholders (`0.0`)** — populating them is
implementation-task work, done by researching each line item individually (targeted
searches per item, e.g. "cost to install a toilet New Hampshire," not backed out of a
blended project-total figure). Today's brainstorming research (bathroom $15k-27.5k
project totals; kitchen $325-1600/sqft by tier; roofing $5.50-8.50/sqft; electrical panel
$1,725-5,175, rewire $6-10/sqft, knob-and-tube add-on $10k-30k) gives sanity-check bounds
the implementation's per-line-item numbers should sum to, but isn't a substitute for
researching the individual line items directly.

**Roofing and electrical have no `tiers` key** — roofing is single-tier per the user's
explicit call (landlords use asphalt shingle almost universally; a luxury/metal tier was
considered and rejected as not useful for rental-investment decisions). Electrical's line
items are priced flat (not tiered) since panel/rewire work is about code compliance and
capacity, not a quality-tier choice the way finishes are.

**The knob-and-tube line item's `trigger`** is evaluated against the property's
`year_built` (already present in the `Property` model from the ingest pipeline) — the
engine surfaces/includes it automatically for pre-1960 properties rather than relying on
the user to remember, since nearly every prospect seen in this pipeline so far is
1880s-1920s construction where this is a real, likely-needed cost.

## Estimation engine (`lib/rehab_cost.py`)

Pure functions, no I/O:

```python
def estimate_project(project_type: str, sqft: float, reference: dict,
                     tier: str | None = None,
                     fixture_counts: dict[str, int] | None = None,
                     year_built: int | None = None) -> ProjectEstimate:
    ...

def total_rehab_cost(estimates: list[ProjectEstimate]) -> RehabTotal:
    ...
```

For each line item in the chosen project type:
- `unit == "sqft"`: `line_cost = (parts_rate + labor_rate) * sqft`, using the tiered rate
  if the project type has tiers, else the flat rate.
- `unit == "each"`: `line_cost = (parts_rate + labor_rate) * fixture_counts.get(name, 1)`
  — defaults to a count of 1 per fixture type unless overridden (e.g. "2 toilets").
- A line item with a `trigger` is only included if the trigger condition evaluates true
  against `year_built` (or omitted/flaggable if `year_built` is unknown — the engine
  should not silently assume pre- or post-1960 when the data is missing; it should note
  the ambiguity rather than guess).

`ProjectEstimate` carries per-line-item parts/labor/subtotal plus a project total.
`total_rehab_cost` sums multiple `ProjectEstimate`s (e.g. bathroom + electrical for the
same property) into a grand total, still broken out per project.

## Skill (`estimate-rehab`)

Conversational invocation, e.g.: *"estimate rehab for 352 Portland St: bathroom remodel
60 sqft economy, electrical (pre-1960, panel upgrade + general rewire) 4358 sqft."* Per
the SKILL.md's instructions, Claude constructs a JSON project-list (project type, tier,
sqft, fixture-count overrides, year_built) and pipes it into `estimate.py`, which loads
the NH Seacoast reference file, calls `lib.rehab_cost`, and renders **markdown only**
(matching the user's chosen output format) — a per-line-item table per project (quantity,
parts rate, labor rate, subtotal), a per-project total, and a grand total across every
project specified for that property. No JSON output, no config/API-key dependency (this
skill needs no external API — everything is local reference data).

## Error handling

- Unknown `project_type` (not in the reference file): clear error naming the valid types,
  not a silent zero-cost result.
- `year_built` missing when a triggered line item (knob-and-tube) is relevant: flag it as
  "unknown — verify wiring age" in the output rather than silently including or excluding
  the cost.
- `tier` supplied for a non-tiered project type (roofing, electrical), or omitted for a
  tiered one (bathroom, kitchen): clear error, since a silently-wrong tier default would
  misstate the estimate.

## Testing

Hand-checked worked examples (same TDD approach as the rest of the plugin), covering:
- One `sqft`-unit line item computed by hand at both tiers.
- One `each`-unit line item with a fixture-count override (e.g. 2 toilets).
- The knob-and-tube trigger firing for a pre-1960 `year_built` and not firing for a
  post-1960 one, plus the "unknown year_built" ambiguity case.
- Multi-project summing (`total_rehab_cost` across e.g. bathroom + electrical) producing
  the correct grand total from the correct per-project subtotals.
- The reference-file-driven design means these tests can use a small inline test fixture
  reference dict rather than depending on the full NH Seacoast file's real (researched)
  numbers — real-number accuracy is validated by the user reviewing the reference file
  directly, not by unit tests asserting specific dollar figures.

## Open items for the implementation plan

- Research and populate every line item's `parts`/`labor` rate in
  `references/rehab-costs-nh-seacoast.json` individually (not backed out of blended
  project totals), with each line item documenting its source and research date.
- Confirm the exact kitchen remodel line-item breakdown (cabinets, countertops,
  appliances, plumbing, electrical, flooring, backsplash) and whether any of those are
  more naturally priced `each`/linear-foot rather than `sqft` (e.g. cabinets are often
  priced per linear foot of run, not per sqft of kitchen floor) — flagged during
  brainstorming as a real design nuance not fully resolved.
- Confirm the exact bathroom remodel line-item list (the design doc's example above is
  illustrative, not final).
