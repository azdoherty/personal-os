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
