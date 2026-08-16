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
