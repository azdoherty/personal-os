# Workout Plugin — Design Spec

**Date:** 2026-08-15
**Status:** Approved design, pending implementation plan
**Location:** `plugins/workout/` (third plugin in the `personal-os` marketplace)

## 1. Purpose

A Claude Code plugin that builds **progressive home strength programs** tailored to the
equipment you own and any physical constraints you have, and outputs them as
printable, fill-in trackers. It also advises on high-value equipment gaps and hands
off to the existing `research` plugin when you want to actually buy gear.

Designed local-first and extensible so its core engine can later drive an adaptive,
phone-based agentic application with no cloud infrastructure.

## 2. Scope (v1)

**In scope:** progressive resistance/strength programming — bodyweight through loaded —
that is **equipment-aware** and **injury/constraint-aware** (e.g. elbow tendinosis →
arm-free substitutions). One-shot program generation with progression baked in.

**Out of scope (v1, non-goals):**
- Cardio/conditioning and mobility/warm-up modules
- Multi-goal engine (hypertrophy/fat-loss/endurance selection)
- Adaptive log-and-replan loop (v1 ships the *data model* for it, not the loop)
- Cloud sync / accounts / any server infrastructure
- Nutrition
- Medical or physical-therapy advice (the plugin is not a PT; outputs carry a disclaimer)

## 3. Architecture

Follows the marketplace → plugin → skill pattern of `research` and `rental`: thin
`SKILL.md` skills over a stdlib `lib/`, a `references/` data layer, appended to
`.claude-plugin/marketplace.json`.

```
plugins/workout/
  .claude-plugin/plugin.json
  skills/
    equipment-intake/SKILL.md        # collect + persist equipment profile
    program-builder/SKILL.md         # orchestrator: inputs -> program -> outputs
    equipment-advisor/SKILL.md       # gap analysis + research handoff
  lib/                               # stdlib-only Python, unit-tested
    model.py                         # Program schema + validation
    store.py                         # SQLite persistence (stdlib sqlite3)
    exercises.py                     # exercise DB loader + equipment/constraint filtering
    templates.py                     # curated template loader
    generator.py                     # principle-based program generation / remix
    progression.py                   # progression engine
    render.py                        # markdown / CSV / JSON renderers
    seed.py                          # seed references/*.json -> SQLite
    tests/                           # pytest
  references/
    exercises.json                   # exercise DB (source-of-truth, git-versioned)
    templates/*.json                 # curated progressive program templates
    equipment.json                   # gear catalog + value ratings
    sources.md                       # vetted methodology/evidence index + reading list
```

**Engine lives in `lib/`, not the skills**, so it is liftable into the future agentic
app. Skills are thin CLI wrappers that call `lib/`.

## 4. Program engine

### 4.1 Data model (`Program`)

The program is one serializable object; SQLite is the store, the JSON below is the
export/interchange view.

```
Program
  meta:        level, goal, days_per_week, session_minutes,
               equipment_profile, constraints[], created,
               source (template_id | "generated")
  progression: model ("double-progression" | "linear" | "variation-ladder"),
               block_weeks
  weeks[]:
    sessions[]:
      exercises[]:
        exercise_id, name, movement_pattern, sets, reps,
        load { type, value|null, progression_rule }, tempo, rest, notes
        log  { date, sets_done, reps_done, load_used, rpe, pain }  # reserved, empty in v1
```

The empty `log` block is the adaptive-later / phone-logging hook. v1 never writes it.

### 4.2 Build flow (inside `program-builder`)

1. **Resolve inputs** — level, equipment profile, constraints, days/week, session length.
2. **Filter the exercise pool** — exercises are tagged by required equipment *and*
   constraint flags (grip / arm-load / overhead / spinal-load / impact). Keep those the
   user *has* and is *allowed*; bucket by movement pattern
   (squat, hinge, push, pull, loaded-carry, core).
3. **Select** — match the best curated template by level+equipment+days; if none fits or
   the user wants to remix, the **generator** assembles one from the eligible pool using
   pattern-balance rules. Same output shape either way.
4. **Apply progression** across the block.
5. **Emit `Program` → persist to SQLite → render** outputs.

### 4.3 Progression ("near nothing → work up")

Each exercise sits on a **variation ladder** (regression → progression); a true beginner
enters at the easiest rung and climbs. The engine advances three levers in order:
**reps** (double-progression within a range) → **load or harder variation** → **volume**.
Loaded lifts use linear progression; bodyweight uses rep-then-variation. A light
**RPE/pain cap** keeps it autoregulated and is where injury constraints stay honored
week to week.

### 4.4 Templates and generator share one model

A curated template is a pre-authored `Program` JSON (partially parameterized). The
generator produces the same shape, so renderers and the progression engine treat both
identically. "Remix" = swap same-pattern exercises from the eligible pool, or regenerate
a session.

## 5. Equipment intake, advisor & research handoff

### 5.1 `equipment-intake`

A grouped checklist (none/bodyweight → bands → dumbbells fixed/adjustable → kettlebells →
barbell + plates → rack → bench → pull-up bar → weighted vest → sled → cardio machines).
Saves a normalized **equipment profile** (set of equipment IDs) to the local SQLite
store. Re-runnable when gear changes. Equipment IDs map directly to exercise-DB tags.

### 5.2 `equipment-advisor`

1. **Coverage** — which movement patterns current gear unlocks vs. leaves thin/missing.
2. **High-ROI gaps** — for each `equipment.json` entry, how many new exercises/patterns it
   unlocks, weighted by value rating and cost/space tier; ranked by unlock-value per
   dollar & footprint.
3. **Constraint-aware** — with elbow constraints active, up-weights arm-free unlocks
   (sled, belt squat, leg press), down-weights grip-heavy gear.
4. **YAGNI guard** — flags redundant/low-value gear so it also talks the user *out* of
   purchases.

### 5.3 Research handoff

When the user wants to buy ("I want a squat rack"), the advisor hands the need to the
`research` plugin's `literature-review` skill (by-path invocation, the same pattern
`literature-review` uses internally), passing a structured purchase query with context
(budget, space, arm-free preference). Boundary: **workout decides *what gear helps and
why*; research decides *which product is good value***. No duplicated logic.

## 6. Storage (local-first, no cloud)

**SQLite is the system of record**, one local file (plugin config dir now; app private
storage later), via stdlib `sqlite3` — consistent with the repo's no-pip-deps convention.

Core tables:
- `equipment_profile` — what the user owns
- `exercises` — the exercise DB (seeded from `references/exercises.json`)
- `equipment_catalog` — advisor gear (seeded from `references/equipment.json`)
- `sources` — the source index (seeded from `references/sources.md`)
- `programs` — program meta
- `sessions`, `program_exercises` — program structure
- `logs` — reserved logging tables (empty in v1, ready for adaptive/phone logging)

Curated `references/*` stay the **git-versioned source-of-truth** and are seeded into
SQLite on init (`seed.py`). **Backup = copy one file** to Google Drive / Dropbox / anywhere,
plus a JSON export for portability. This model carries directly into the Android app —
local DB, user-controlled backup, zero cloud dependency.

## 7. Outputs

All outputs are pure renders of the SQLite data (no logic in renderers):
- **Markdown** — canonical printable program + tracker ("print and fill out")
- **CSV** — printable log grid (row per set/day); also the import path once logging goes digital
- **HTML artifact** — polished, theme-aware on-screen/printable version
- **JSON export** — interchange + backup, feeding the future app/agent

## 8. Source index

`references/sources.md` (→ `sources` table): a vetted index of the methodologies and
evidence the templates are built on. Per entry: id, title, author/org, URL, topic tags,
trust tier, and which templates/patterns it informs — plus a "go deeper" reading list.
Workout-specific (established programs, strength standards, rehab loading protocols,
ACSM/NSCA-grade sources). Every generated program can cite *why* it is built the way it is.

## 9. Testing

`pytest` on `lib/`, mirroring `rental`'s approach:
- program generation produces valid `Program` objects for each level/equipment combo
- progression engine advances levers correctly and honors RPE/pain caps
- equipment + constraint filtering excludes/substitutes correctly (e.g. arm-free)
- renderers produce stable markdown/CSV/JSON
- SQLite seed + round-trip (write program, read back identical)

## 10. Future direction (design-influencing, not built in v1)

- **Adaptive log-and-replan**: fill the `logs` tables from user input; a replan step
  consumes actuals to adjust the next block.
- **Android agentic app**: the `lib/` engine + SQLite schema are the portable core; a
  mobile agent reads/writes the same DB. Local-first + file backup means no cloud infra.

## 11. Open questions

None blocking. Content-authoring volume (how many templates / how deep the exercise DB
ships in v1) to be sized in the implementation plan; v1 targets a minimal but complete
vertical slice (beginner bodyweight + one loaded tier) rather than exhaustive coverage.
