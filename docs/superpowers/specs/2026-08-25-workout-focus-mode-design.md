# Workout Plugin — Focus-Mode Split Routines & Ladder-Notes Fix — Design Spec

**Date:** 2026-08-25
**Status:** Approved design, pending implementation plan
**Location:** `plugins/workout/` (existing plugin, extends the v1 full-body engine)

## 1. Purpose

Two changes, bundled because they touch the same code paths:

1. **Focus-mode split routines.** Today `program-builder` only produces full-body
   sessions (one exercise per movement pattern: squat/hinge/push/pull/core/carry).
   There is no way to ask for a single-focus session ("core day," "leg day," "arm
   day") with several exercises targeting that focus, sized to the user's actual
   session length. This was discovered by hand-testing the plugin against a real
   request ("an ab routine, no equipment, starting low, over a month") that it
   could not fulfill — the generator dropped core work entirely at a short time
   budget and, even unconstrained, offered only one repeating core exercise.
2. **Ladder-notes bug fix.** When an exercise climbs its variation ladder across
   weeks (e.g. Dead Bug → Plank), the printed exercise name and reps update
   correctly but the instructional `notes` text stays frozen on whichever exercise
   was active when the slot was first assembled — a real, previously undiscovered
   defect found during the same hand-test.

## 2. Scope

**In scope:**
- A `--focus` flag on `program-builder`'s `build.py` accepting a comma-separated
  list from `{core, legs, arms}`, cycling across the requested `--days` to build a
  split routine in one call (e.g. `--focus core,legs,arms --days 6` → core, legs,
  arms, core, legs, arms).
- A new `sub_category` field on exercise DB entries, used to give focus-mode
  sessions real variety (multiple *different* exercises per focus) instead of one
  exercise repeated for the whole block.
- Restructuring the existing `core_bw` ladder into four sub-category ladders
  (anti-extension, anti-rotation, flexion, hip-flexor endurance), matching the
  four-category structure already validated by hand for the user.
- New no-equipment/low-equipment arm exercises (triceps: diamond push-up, pike
  push-up, chair dip; biceps/back: reusing the existing table inverted row,
  newly tagged) — with an explicit, disclosed limitation that true bodyweight
  bicep isolation doesn't really exist, so a zero-equipment "arm day" is
  triceps-heavy unless the user owns a chair or table.
- A new `chair` equipment-catalog entry (cost/space tier `none`, like the
  existing `sturdy_table`).
- A new focus-aware generation path in `lib/generator.py` that composes a
  session from multiple sub-categories within a focus, sized by session length,
  reusing the existing progression engine (ladder / double-progression)
  unchanged.
- Fixing `_build_ladder_exercise` so a climbing exercise's `notes` come from the
  currently-active rung, not the slot's original assembly.
- Updating any existing full-body tests whose expected exercise picks change as
  a side effect of splitting `core_bw` into four groups (a real, identified
  regression risk — see §7).

**Out of scope (this round):**
- Curated templates for focus mode (templates stay full-body-only in v1; a
  `--focus` request always uses the generator path, never template matching).
- Push/pull/legs-style "textbook" splits, or any focus beyond the three named
  (`core`, `legs`, `arms`).
- Multiple exercises *within* the same sub-category in one session (one
  exercise per sub-category, same as full-body's one-per-pattern model).
- Adaptive/logged feedback changing exercise selection — this is still a
  one-shot generated block, consistent with the rest of v1.

## 3. Data model additions

### 3.1 `sub_category` field

Added to `references/exercises.json` entries. Optional; when absent, the
exercise's `movement_pattern` acts as its own sub-category (this is why `legs`
needs no new tagging — `squat` and `hinge` already function as two distinct
sub-categories at the pattern level).

Used values this round: `anti_extension`, `anti_rotation`, `flexion`,
`hip_flexor_endurance` (core), `triceps`, `biceps` (arms).

### 3.2 Core ladder restructuring

`core_bw` (today: Dead Bug → Plank → Side Plank, one ladder) splits into four
ladders:

| Ladder group | Sub-category | Rungs (rank 0 → highest) |
|---|---|---|
| `core_antiext_bw` | `anti_extension` | Dead Bug *(existing)* → Plank *(existing, moved)* |
| `core_antirot_bw` | `anti_rotation` | Bird Dog *(new)* → Side Plank, knees *(new)* → Side Plank *(existing, moved, now rank 2)* |
| `core_flexion_bw` | `flexion` | Curl-Up *(new)* → Bicycle Crunch *(new)* |
| `core_hipflexor_bw` | `hip_flexor_endurance` | Knee Tuck Hold *(new)* → Leg Raise, bent knee *(new)* → Leg Raise, straight *(new)* |

All new exercises: bodyweight, no equipment, no constraint flags (matching the
existing core exercises' profile) except where noted.

### 3.3 New arm exercises

| exercise_id | Pattern | Sub-category | Equipment | Notes |
|---|---|---|---|---|
| `diamond_pushup` | push | `triceps` | none | Standalone (not a ladder rung) |
| `pike_pushup` | push | `triceps` | none | Standalone |
| `chair_dip` | push | `triceps` | `chair` (new catalog item) | Standalone |

Existing `table_inverted_row` / `table_inverted_row_bent` gain
`sub_category: "biceps"` (no other change — they stay in the `pull_bw` ladder
for full-body use, and are also the biceps pick for arms-focus mode).

`references/equipment.json` gains one entry: `chair` — `cost_tier: "none"`,
`space_tier: "none"`, matching `sturdy_table`'s treatment (most basements have
one; tracked rather than assumed, for consistency).

**Disclosed limitation (goes in the plan's docs task, not hidden):** a user
with zero furniture gets triceps-only arm work (diamond push-up, pike
push-up); the biceps pick requires owning a chair or table. This is a
real constraint of bodyweight training, not a gap to engineer around this
round.

## 4. Focus resolution & session composition

```
FOCUS_PATTERNS = {
    "legs": ("squat", "hinge", "carry"),
    "core": ("core",),
    "arms": ("push", "pull"),
}
```

Building one focused session:

1. Filter the exercise DB to eligible exercises (existing `is_eligible`,
   unchanged) within the focus's patterns.
2. Bucket the eligible pool by `sub_category`, falling back to
   `movement_pattern` when the field is absent. Order buckets deterministically:
   named sub-categories first (alphabetical), then pattern-fallback buckets —
   so `arms` mode surfaces the dedicated triceps/biceps picks before generic
   push/pull compounds, and `legs`/`core` are unaffected since every one of
   their exercises already has an effective sub-category.
3. Exercise count for the session = `min(number of available buckets,
   max(2, minutes // MINUTES_PER_FOCUS_SLOT))` — the floor of 2 applies only to
   the *minutes-derived* slot count, before capping by available buckets, so a
   focus with just one eligible bucket (e.g. a `legs` day where constraints
   rule out every hinge exercise) still correctly yields one exercise, not two
   from a pool of one. Mirrors the existing `slots_per_session` heuristic but
   with its own constant, since focused single-movement work needs less time
   per exercise than a mixed full-body circuit. `MINUTES_PER_FOCUS_SLOT`
   defaults to 7 (tunable, not load-bearing on any existing behavior).
4. Pick one exercise per selected bucket using the existing
   `_pick_representative` tie-break (prefer equipment-matching, then
   exercise_id) — no new selection logic, just applied per-bucket instead of
   per-pattern.
5. Each picked exercise progresses exactly as today: ladder members via
   `apply_variation_ladder`, standalone members via `_reps_from_db` +
   double-progression. No changes to `progression.py`'s models.
6. A day's session `label` becomes the focus name ("Core", "Legs", "Arms")
   instead of "Session N".

### 4.1 Multi-day cycling

`--focus core,legs,arms --days 6` assigns `focus_list[day_index % len(focus_list)]`
to each day — cycling, not truncating. `--focus core --days 3` (single focus)
degrades to "the same focus every day," which is also a valid, common request
(exactly your original ask). Every day sharing a focus gets the *same* exercise
selection (deterministic), progressing together across the block — this
matches how full-body days already work when the same pattern repeats.

### 4.2 CLI & output surface

- New `--focus` argument on `build.py`, comma-separated, validated against
  `{core, legs, arms}` via a new `validate_focus()` in `lib/validation.py`
  (same pattern as the existing constraint/equipment token validation — reject
  loudly on typos, never silently drop).
- When `--focus` is supplied: template matching is skipped entirely (§2, out of
  scope), `generator.generate_focus_program(...)` is called instead of
  `generate_program`/`build_program_from_template`, and `meta.source` is set to
  `"generated-focus"` (vs. today's `"generated"`) so downstream renderers and
  any future consumer can distinguish the two, `meta.goal` becomes a readable
  summary of the focus list (e.g. `"split: core, legs, arms"`).
- When `--focus` is omitted: zero behavior change. Every existing full-body
  code path, test, and CLI invocation is unaffected.

## 5. Ladder-notes bug fix

`progression.py`'s `apply_variation_ladder` returns a per-week dict built from
the currently-active rung (`exercise_id`, `name`, `reps`, ...) but not `notes`
— so `generator.py`'s `_build_ladder_exercise` falls back to
`entry.get("notes", "")`, the *slot's* static config, which never changes as
the ladder climbs.

**Fix:** `apply_variation_ladder` includes `"notes": rung.get("notes", "")` in
its returned dict; `_build_ladder_exercise` uses that instead of
`entry.get("notes", "")`. Two small, mechanical edits, independent of the
focus-mode work — bundled into the same plan because both touch
`generator.py`'s ladder-building code and are easiest to land together.

## 6. What does NOT change

- `progression.py`'s three models (`linear`, `double-progression`,
  `variation-ladder`) — untouched except the one-field notes fix in §5.
- `store.py`, `render.py`, `seed.py`, `advisor.py`, `templates.py` — untouched.
  Focus-mode programs are still `Program` objects; they save, round-trip, and
  render exactly like full-body ones (§4's `meta.source`/`meta.goal` values are
  just new string content in existing fields, not new fields).
- `equipment-intake`, `equipment-advisor` skills — untouched.
- Full-body generation when `--focus` is not passed — byte-for-byte unchanged
  behavior, though the underlying `core_bw` restructuring changes *which* core
  exercise a full-body session picks (see §7 — this is the one place the two
  changes interact).

## 7. Regression risk: core ladder restructuring affects full-body picks

`_pick_representative`'s tie-break already handles "multiple `ladder_rank == 0`
candidates in one pattern" (sorts alphabetically), but today there's only ever
one such candidate for `core` (`dead_bug`). After splitting `core_bw` into four
groups, there will be **four** rank-0 candidates (`bird_dog`, `curl_up`,
`dead_bug`, `knee_tuck_hold`) — alphabetically, `bird_dog` now wins a
full-body session's core slot, not `dead_bug`.

This is a real, deliberate behavior change (more variety is the point), not a
bug — but it will break any existing test that hardcodes an expected core
`exercise_id` for a full-body scenario. The plan must include: (a) find every
such test via a targeted grep for `dead_bug`/`core_bw` in `lib/tests/`, (b)
update expected values to match the new, intentional selection, (c) re-run the
full suite to confirm nothing else references the old single-ladder shape.

## 8. Testing

Extends the existing `pytest` suite (`cd plugins/workout && python -m pytest
lib/tests -v`), no new tooling:

- `parse`/model-level: `sub_category` round-trips through `to_dict`/`from_dict`
  unaffected (it lives in the exercise DB, not `ProgramExercise` — no model
  change needed there).
- `exercises.py`: bucket-by-`sub_category` helper, tested against a synthetic
  fixture and the real DB.
- `generator.py`: `generate_focus_program` tested for each of the three
  focuses, for multi-focus cycling, for the arm-day equipment-gap case
  (zero-equipment user gets triceps-only), and for the ladder-notes fix
  (mutation-tested the same way every other fix in this codebase has been —
  revert, confirm a test fails, restore).
- `validation.py`: `validate_focus` tested for legal/illegal tokens, same shape
  as the existing constraint/equipment validators.
- `build.py` CLI: at least one end-to-end `--focus` smoke test through
  `test_build_cli.py`'s existing pattern (real `:memory:` DB, real build, real
  assertions on the output).
- Full-body regression: every existing test still passes, with the `core_bw`
  split's known, intentional exercise-pick changes (§7) updated deliberately.

## 9. Open questions

None blocking. Exact `MINUTES_PER_FOCUS_SLOT` value (7) and the precise
bucket-ordering tie-break are implementation-level judgment calls within this
spec's stated mechanism, not open design questions.
