# Workout Plugin — Focus-Mode Split Routines & Ladder-Notes Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--focus {core,legs,arms}` mode to `program-builder` that builds real multi-exercise split-routine sessions (not the one-exercise-per-pattern full-body model), and fix the bug where a climbing ladder exercise keeps showing the previous rung's instructional notes.

**Architecture:** A new `sub_category` field on exercise DB entries gives focus-mode real variety within one movement pattern (core splits into anti-extension/anti-rotation/flexion/hip-flexor; arms gets new isolation content). A new `generate_focus_program` in `lib/generator.py` reuses every existing building block (progression engine, `_pick_representative`, `_build_ladder_exercise`/`_build_loaded_exercise`) — it only changes *which* exercises get bucketed and picked. The notes fix is two small edits to the ladder-building path, landed independently since both changes touch the same functions.

**Tech Stack:** Stdlib-only Python (unchanged from the rest of `plugins/workout`). `pytest` for tests.

## Global Constraints

- Stdlib-only Python for all `lib/` runtime code; `pytest` remains the accepted test-only dependency.
- No cloud infrastructure; SQLite stays local-first (unchanged by this plan — no schema changes).
- Every existing full-body code path, CLI invocation, and test must keep passing unmodified when `--focus` is not supplied. This plan adds a path; it must not perturb the existing one.
- Approved design spec: `docs/superpowers/specs/2026-08-25-workout-focus-mode-design.md` — this plan implements it in full.

---

## Task 1: Restructure the core ladder, add core + arm content, add `chair` equipment

**Files:**
- Modify: `plugins/workout/references/exercises.json`
- Modify: `plugins/workout/references/equipment.json`
- Modify: `plugins/workout/references/templates/bodyweight_beginner_3day.json`

**Interfaces:**
- Consumes: nothing (data-only task).
- Produces: the restructured/expanded exercise DB and equipment catalog every later task reads. New `sub_category` field (optional, string) on exercise entries. New ladder groups `core_antiext_bw`, `core_antirot_bw`, `core_flexion_bw`, `core_hipflexor_bw` (the old `core_bw` no longer exists). New equipment id `chair`.

This is a pure data change — no Python code in this task. `lib/exercises.py`'s `sub_category` handling comes in Task 3.

- [ ] **Step 1: Rewrite the exercise database**

Replace the full contents of `plugins/workout/references/exercises.json` with:

```json
[
  {"exercise_id": "box_squat", "name": "Box Squat", "movement_pattern": "squat", "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw", "ladder_rank": 0, "default_reps": "10-15", "notes": "Sit back onto a chair or box, stand back up. Lightly touch and go."},
  {"exercise_id": "bodyweight_squat", "name": "Bodyweight Squat", "movement_pattern": "squat", "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw", "ladder_rank": 1, "default_reps": "12-15", "notes": "Feet shoulder-width, sit the hips back and down, chest tall."},
  {"exercise_id": "bulgarian_split_squat_bw", "name": "Bulgarian Split Squat (bodyweight)", "movement_pattern": "squat", "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw", "ladder_rank": 2, "default_reps": "8-10 / leg", "notes": "Rear foot elevated on a chair; lower the back knee toward the floor."},

  {"exercise_id": "glute_bridge", "name": "Glute Bridge", "movement_pattern": "hinge", "equipment_required": [], "constraint_flags": [], "ladder_group": "hinge_bw", "ladder_rank": 0, "default_reps": "12-15", "notes": "Lie on your back, drive the hips up, squeeze the glutes at the top."},
  {"exercise_id": "single_leg_glute_bridge", "name": "Single-Leg Glute Bridge", "movement_pattern": "hinge", "equipment_required": [], "constraint_flags": [], "ladder_group": "hinge_bw", "ladder_rank": 1, "default_reps": "10-12 / leg", "notes": "Same as glute bridge with one foot lifted."},
  {"exercise_id": "single_leg_rdl_bw", "name": "Single-Leg RDL (bodyweight)", "movement_pattern": "hinge", "equipment_required": [], "constraint_flags": [], "ladder_group": "hinge_bw", "ladder_rank": 2, "default_reps": "8-10 / leg", "notes": "Hinge at the hips on one leg, arms free for balance; keep the back flat."},

  {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "movement_pattern": "push", "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push_bw", "ladder_rank": 0, "default_reps": "8-12", "notes": "Hands on a sturdy elevated surface, body in a straight line."},
  {"exercise_id": "pushup", "name": "Push-Up", "movement_pattern": "push", "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push_bw", "ladder_rank": 1, "default_reps": "10-15", "notes": "Hands on the floor, body in a straight line, elbows ~45 degrees from the torso."},
  {"exercise_id": "decline_pushup", "name": "Decline Push-Up", "movement_pattern": "push", "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push_bw", "ladder_rank": 2, "default_reps": "8-12", "notes": "Feet elevated on a chair or step."},

  {"exercise_id": "table_inverted_row_bent", "name": "Table Inverted Row (bent knees)", "movement_pattern": "pull", "sub_category": "biceps", "equipment_required": ["sturdy_table"], "constraint_flags": ["arm-load", "grip"], "ladder_group": "pull_bw", "ladder_rank": 0, "default_reps": "8-12", "notes": "Lie under a sturdy table, knees bent, pull the chest to the table edge."},
  {"exercise_id": "table_inverted_row", "name": "Table Inverted Row", "movement_pattern": "pull", "sub_category": "biceps", "equipment_required": ["sturdy_table"], "constraint_flags": ["arm-load", "grip"], "ladder_group": "pull_bw", "ladder_rank": 1, "default_reps": "8-10", "notes": "Same as the bent-knee version with legs straight."},

  {"exercise_id": "dead_bug", "name": "Dead Bug", "movement_pattern": "core", "sub_category": "anti_extension", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_antiext_bw", "ladder_rank": 0, "default_reps": "10-12 / side", "notes": "Lower the opposite arm and leg slowly, keep the low back pressed to the floor."},
  {"exercise_id": "plank", "name": "Plank", "movement_pattern": "core", "sub_category": "anti_extension", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_antiext_bw", "ladder_rank": 1, "default_reps": "30-45s", "notes": "Forearms and toes on the floor, body in a straight line."},

  {"exercise_id": "bird_dog", "name": "Bird Dog", "movement_pattern": "core", "sub_category": "anti_rotation", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_antirot_bw", "ladder_rank": 0, "default_reps": "8-10 / side", "notes": "Extend the opposite arm and leg slowly, pause at full extension, keep the hips square."},
  {"exercise_id": "side_plank_knees", "name": "Side Plank (knees bent)", "movement_pattern": "core", "sub_category": "anti_rotation", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_antirot_bw", "ladder_rank": 1, "default_reps": "15-20s / side", "notes": "Knees bent and stacked, prop up on one forearm, hips lifted."},
  {"exercise_id": "side_plank", "name": "Side Plank", "movement_pattern": "core", "sub_category": "anti_rotation", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_antirot_bw", "ladder_rank": 2, "default_reps": "20-30s / side", "notes": "Stack the feet, prop up on one forearm, hips lifted."},

  {"exercise_id": "curl_up", "name": "Curl-Up", "movement_pattern": "core", "sub_category": "flexion", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_flexion_bw", "ladder_rank": 0, "default_reps": "10-12", "notes": "Lift the shoulder blades a few inches off the floor, low back stays down -- this isn't a sit-up."},
  {"exercise_id": "bicycle_crunch", "name": "Bicycle Crunch", "movement_pattern": "core", "sub_category": "flexion", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_flexion_bw", "ladder_rank": 1, "default_reps": "10-15 / side", "notes": "Opposite elbow to opposite knee, slow and controlled, not a speed drill."},

  {"exercise_id": "knee_tuck_hold", "name": "Knee Tuck Hold", "movement_pattern": "core", "sub_category": "hip_flexor_endurance", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_hipflexor_bw", "ladder_rank": 0, "default_reps": "15-20s", "notes": "Seated or lying, knees pulled toward the chest, hold without the low back rounding."},
  {"exercise_id": "leg_raise_bent", "name": "Leg Raise (bent knee)", "movement_pattern": "core", "sub_category": "hip_flexor_endurance", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_hipflexor_bw", "ladder_rank": 1, "default_reps": "10-12", "notes": "Lying on your back, knees bent to 90 degrees, lower and raise without arching the low back."},
  {"exercise_id": "leg_raise_straight", "name": "Leg Raise (straight leg)", "movement_pattern": "core", "sub_category": "hip_flexor_endurance", "equipment_required": [], "constraint_flags": [], "ladder_group": "core_hipflexor_bw", "ladder_rank": 2, "default_reps": "8-10", "notes": "Same as the bent-knee version with legs straight -- stop the set before the low back arches."},

  {"exercise_id": "diamond_pushup", "name": "Diamond Push-Up", "movement_pattern": "push", "sub_category": "triceps", "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "6-10", "notes": "Hands together under the chest, thumbs and index fingers touching, elbows stay close to the torso."},
  {"exercise_id": "pike_pushup", "name": "Pike Push-Up", "movement_pattern": "push", "sub_category": "triceps", "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "6-10", "notes": "Hips high, hands and feet on the floor forming an inverted V, lower the crown of the head toward the floor."},
  {"exercise_id": "chair_dip", "name": "Chair Dip", "movement_pattern": "push", "sub_category": "triceps", "equipment_required": ["chair"], "constraint_flags": ["arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Hands on a sturdy chair edge behind you, heels forward, lower and press back up."},

  {"exercise_id": "db_goblet_squat", "name": "DB Goblet Squat", "movement_pattern": "squat", "equipment_required": ["dumbbell"], "constraint_flags": ["grip"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Hold one dumbbell vertically at the chest, squat between the knees."},
  {"exercise_id": "db_romanian_deadlift", "name": "DB Romanian Deadlift", "movement_pattern": "hinge", "equipment_required": ["dumbbell"], "constraint_flags": ["grip"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Hinge at the hips, dumbbells stay close to the legs, slight knee bend."},
  {"exercise_id": "db_bench_press_floor", "name": "DB Floor Press", "movement_pattern": "push", "equipment_required": ["dumbbell"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Lie on the floor, press dumbbells straight up over the shoulders."},
  {"exercise_id": "db_bench_press", "name": "DB Bench Press", "movement_pattern": "push", "equipment_required": ["dumbbell", "bench"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Same as the floor press with a full range of motion on a bench."},
  {"exercise_id": "db_bent_over_row", "name": "DB Bent-Over Row", "movement_pattern": "pull", "equipment_required": ["dumbbell"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Hinge forward ~45 degrees, pull the elbows past the ribs."},
  {"exercise_id": "db_farmer_carry", "name": "DB Farmer's Carry", "movement_pattern": "carry", "equipment_required": ["dumbbell"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "2-4 trips", "notes": "Trips of ~30m each, walk tall with shoulders back."},
  {"exercise_id": "pullup_band_assisted", "name": "Band-Assisted Pull-Up", "movement_pattern": "pull", "equipment_required": ["pull_up_bar", "resistance_band"], "constraint_flags": ["grip", "arm-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "4-8", "notes": "Loop a band over the bar and under a knee or foot for assistance."},

  {"exercise_id": "weighted_vest_split_squat", "name": "Weighted Vest Split Squat", "movement_pattern": "squat", "equipment_required": ["weighted_vest"], "constraint_flags": [], "ladder_group": null, "ladder_rank": null, "default_reps": "8-10 / leg", "notes": "Wear the vest, hands free at your sides for balance only -- no grip or arm load."},
  {"exercise_id": "sled_push", "name": "Sled Push (hip harness)", "movement_pattern": "squat", "equipment_required": ["sled"], "constraint_flags": [], "ladder_group": null, "ladder_rank": null, "default_reps": "3-5 trips", "notes": "Pull from a hip harness, hands empty at your sides -- no grip or arm load."},
  {"exercise_id": "belt_squat", "name": "Belt Squat", "movement_pattern": "squat", "equipment_required": ["belt_squat_rig"], "constraint_flags": [], "ladder_group": null, "ladder_rank": null, "default_reps": "8-12", "notes": "Load hangs from a belt around the hips -- no grip or arm load."},

  {"exercise_id": "barbell_back_squat", "name": "Barbell Back Squat", "movement_pattern": "squat", "equipment_required": ["barbell", "rack"], "constraint_flags": ["grip", "spinal-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "5-8", "notes": "Bar racked across the upper back, squat to depth."},
  {"exercise_id": "barbell_romanian_deadlift", "name": "Barbell Romanian Deadlift", "movement_pattern": "hinge", "equipment_required": ["barbell"], "constraint_flags": ["grip", "spinal-load"], "ladder_group": null, "ladder_rank": null, "default_reps": "6-10", "notes": "Hinge at the hips holding the bar, bar stays close to the legs."}
]
```

Changes versus the current file, for your own tracking: `dead_bug`/`plank` gained `sub_category: "anti_extension"` and moved from `ladder_group: "core_bw"` to `"core_antiext_bw"`; `side_plank` gained `sub_category: "anti_rotation"`, moved to `"core_antirot_bw"`, and is now `ladder_rank: 2` (unchanged numerically, new group); `table_inverted_row`/`table_inverted_row_bent` gained `sub_category: "biceps"` (no other change); 10 new exercises were added (`bird_dog`, `side_plank_knees`, `curl_up`, `bicycle_crunch`, `knee_tuck_hold`, `leg_raise_bent`, `leg_raise_straight`, `diamond_pushup`, `pike_pushup`, `chair_dip`).

- [ ] **Step 2: Add the `chair` equipment entry**

In `plugins/workout/references/equipment.json`, insert a new entry after `sturdy_table` (before the closing `bench` entry), so the file reads:

```json
[
  {"equipment_id": "dumbbell", "name": "Adjustable Dumbbells (pair)", "cost_tier": "medium", "space_tier": "small", "approx_cost_usd": 250, "notes": "The single highest-value first purchase; unlocks squat, hinge, push, pull, and carry patterns."},
  {"equipment_id": "resistance_band", "name": "Resistance Band Set", "cost_tier": "low", "space_tier": "small", "approx_cost_usd": 30, "notes": "Cheap assistance for pull-up progressions."},
  {"equipment_id": "pull_up_bar", "name": "Doorway Pull-Up Bar", "cost_tier": "low", "space_tier": "small", "approx_cost_usd": 30, "notes": "Needed alongside a resistance band for assisted pull-ups."},
  {"equipment_id": "weighted_vest", "name": "Weighted Vest (20-40 lb)", "cost_tier": "medium", "space_tier": "small", "approx_cost_usd": 100, "notes": "Loads squat-pattern work with zero grip or arm involvement -- useful when avoiding grip/arm-load."},
  {"equipment_id": "sled", "name": "Drag Sled / Loaded Tire Rig", "cost_tier": "low", "space_tier": "medium", "approx_cost_usd": 40, "notes": "Heavy leg work pulled from a hip harness -- arm-free."},
  {"equipment_id": "belt_squat_rig", "name": "Belt Squat Machine", "cost_tier": "high", "space_tier": "large", "approx_cost_usd": 800, "notes": "Heaviest arm-free squat option; a big-ticket item."},
  {"equipment_id": "barbell", "name": "Barbell + Plates", "cost_tier": "medium", "space_tier": "medium", "approx_cost_usd": 300, "notes": "Enables the heaviest loaded squat/hinge work; grip- and spine-loading."},
  {"equipment_id": "rack", "name": "Squat Rack", "cost_tier": "high", "space_tier": "large", "approx_cost_usd": 400, "notes": "Needed to safely rack/unrack a loaded barbell squat."},
  {"equipment_id": "sturdy_table", "name": "Sturdy Table (for inverted rows)", "cost_tier": "none", "space_tier": "none", "approx_cost_usd": 0, "notes": "Most households already have one; the free way to train the pull pattern with no other equipment."},
  {"equipment_id": "chair", "name": "Sturdy Chair", "cost_tier": "none", "space_tier": "none", "approx_cost_usd": 0, "notes": "Most households already have one; unlocks chair dips for triceps-focused arm work."},
  {"equipment_id": "bench", "name": "Adjustable Bench", "cost_tier": "medium", "space_tier": "medium", "approx_cost_usd": 150, "notes": "Upgrades floor pressing to a full-range bench press."}
]
```

- [ ] **Step 3: Fix the now-broken curated template's ladder group references**

`plugins/workout/references/templates/bodyweight_beginner_3day.json` references `"ladder_group": "core_bw"` twice (day 1 and day 2 sessions). That group no longer exists after Step 1 -- without this fix, both core slots would silently drop (via `LadderUnavailable` being caught in `build_program_from_template`), and the curated bodyweight template would quietly lose its core work.

In `plugins/workout/references/templates/bodyweight_beginner_3day.json`, change both occurrences of:

```json
        {"ladder_group": "core_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "n/a", "rest": "30s", "notes": "Move slowly; keep the low back pressed to the floor."}
```

to:

```json
        {"ladder_group": "core_antiext_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "n/a", "rest": "30s", "notes": "Move slowly; keep the low back pressed to the floor."}
```

(Anti-extension -- Dead Bug climbing to Plank -- is the most foundational, beginner-appropriate core pattern, matching what used to be `core_bw`'s own rank 0-1.)

- [ ] **Step 4: Verify the JSON is valid and internally consistent**

Run:
```bash
python -c "
import json
exercises = json.load(open('plugins/workout/references/exercises.json'))
equipment = json.load(open('plugins/workout/references/equipment.json'))
templates = [
    json.load(open('plugins/workout/references/templates/bodyweight_beginner_3day.json')),
    json.load(open('plugins/workout/references/templates/dumbbell_beginner_3day.json')),
]

assert len(exercises) == 36, len(exercises)
by_id = {e['exercise_id']: e for e in exercises}
assert len(by_id) == len(exercises), 'duplicate exercise_id'

catalog_ids = {i['equipment_id'] for i in equipment}
used_ids = {eid for e in exercises for eid in e['equipment_required']}
assert not (used_ids - catalog_ids), used_ids - catalog_ids
assert 'chair' in catalog_ids

# every ladder group internally uniform on equipment/constraints/pattern
groups = {}
for e in exercises:
    g = e.get('ladder_group')
    if g:
        groups.setdefault(g, []).append(e)
for name, rungs in groups.items():
    assert len({tuple(sorted(r['equipment_required'])) for r in rungs}) == 1, name
    assert len({tuple(sorted(r['constraint_flags'])) for r in rungs}) == 1, name
    assert len({r['movement_pattern'] for r in rungs}) == 1, name
assert 'core_bw' not in groups
assert set(groups) >= {'core_antiext_bw', 'core_antirot_bw', 'core_flexion_bw', 'core_hipflexor_bw'}

# templates only reference ladder groups / exercise ids that exist
for t in templates:
    for session in t['sessions']:
        for entry in session['exercises']:
            if 'ladder_group' in entry:
                assert entry['ladder_group'] in groups, entry['ladder_group']
            else:
                assert entry['exercise_id'] in by_id, entry['exercise_id']

print('OK', len(exercises), 'exercises,', len(equipment), 'equipment items,', len(groups), 'ladder groups')
"
```
Expected: `OK 36 exercises, 11 equipment items, 8 ladder groups`

- [ ] **Step 5: Confirm the existing suite still passes against the new data**

Run: `cd plugins/workout && python -m pytest lib/tests -v`
Expected: all existing tests still pass (they read this data at runtime; nothing here changes any Python code). Note: `test_no_equipment_subset_gets_a_program_that_ignores_the_gear_it_owns` in `test_build_cli.py` sweeps every non-empty subset of the equipment catalog and will now run over `2**11 - 1 = 2047` subsets instead of `1023` -- still fast (a couple of seconds), not a failure.

- [ ] **Step 6: Commit**

```bash
git add plugins/workout/references/exercises.json plugins/workout/references/equipment.json \
    plugins/workout/references/templates/bodyweight_beginner_3day.json
git commit -m "feat(workout): split core ladder into 4 sub-categories, add arm isolation exercises and chair equipment"
```

---

## Task 2: Fix the ladder-notes bug

**Files:**
- Modify: `plugins/workout/lib/progression.py:52-66` (`apply_variation_ladder`)
- Modify: `plugins/workout/lib/generator.py:174-194` (`_build_ladder_exercise`), `:343-363` (`generate_program`'s ladder-entry construction)
- Modify: `plugins/workout/references/templates/bodyweight_beginner_3day.json` (strip now-dead per-slot `notes`)
- Test: `plugins/workout/lib/tests/test_progression.py`, `plugins/workout/lib/tests/test_generator.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `apply_variation_ladder`'s returned dict now includes a `"notes"` key (in addition to `exercise_id`, `name`, `sets`, `reps`, `load_type`, `load_value`). `_build_ladder_exercise`'s built `ProgramExercise.notes` now reflects the currently-active rung, not the slot's static config.

- [ ] **Step 1: Write the failing test for `apply_variation_ladder`**

Add to `plugins/workout/lib/tests/test_progression.py`:

```python


def test_variation_ladder_notes_come_from_the_active_rung_not_a_static_slot_note():
    ladder = [
        {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "default_reps": "8-12",
         "notes": "Hands elevated."},
        {"exercise_id": "pushup", "name": "Push-Up", "default_reps": "10-15",
         "notes": "Hands on the floor."},
    ]
    cfg = {"sets": 3, "weeks_per_rung": 2}
    week1 = prog_mod.apply_variation_ladder(cfg, 1, ladder)
    week3 = prog_mod.apply_variation_ladder(cfg, 3, ladder)
    assert week1["notes"] == "Hands elevated."
    assert week3["notes"] == "Hands on the floor."
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd plugins/workout && python -m pytest lib/tests/test_progression.py::test_variation_ladder_notes_come_from_the_active_rung_not_a_static_slot_note -v`
Expected: FAIL with `KeyError: 'notes'`

- [ ] **Step 3: Fix `apply_variation_ladder`**

In `plugins/workout/lib/progression.py`, change:

```python
    return {
        "exercise_id": rung["exercise_id"],
        "name": rung["name"],
        "sets": exercise_cfg["sets"],
        "reps": rung["default_reps"],
        "load_type": "bodyweight",
        "load_value": None,
    }
```

to:

```python
    return {
        "exercise_id": rung["exercise_id"],
        "name": rung["name"],
        "sets": exercise_cfg["sets"],
        "reps": rung["default_reps"],
        "load_type": "bodyweight",
        "load_value": None,
        "notes": rung.get("notes", ""),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd plugins/workout && python -m pytest lib/tests/test_progression.py -v`
Expected: `10 passed` (9 existing + 1 new)

- [ ] **Step 5: Write the failing test for `_build_ladder_exercise`**

Add to `plugins/workout/lib/tests/test_generator.py`:

```python


def test_ladder_exercise_notes_update_as_the_program_climbs_rungs():
    ladder = [
        {"exercise_id": "box_squat", "name": "Box Squat", "movement_pattern": "squat",
         "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
         "ladder_rank": 0, "default_reps": "10-15",
         "notes": "Sit back onto a chair or box, stand back up."},
        {"exercise_id": "bodyweight_squat", "name": "Bodyweight Squat", "movement_pattern": "squat",
         "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
         "ladder_rank": 1, "default_reps": "12-15",
         "notes": "Feet shoulder-width, sit the hips back and down, chest tall."},
    ]
    entry = {"ladder_group": "squat_bw", "sets": 3, "weeks_per_rung": 1, "tempo": "2-0-2", "rest": "60s"}
    weeks = gen_mod._build_ladder_exercise(entry, ladder, 3, equipment_profile=[], constraints=[])
    assert weeks[0].notes == "Sit back onto a chair or box, stand back up."
    assert weeks[1].notes == "Feet shoulder-width, sit the hips back and down, chest tall."
```

Note this test's `entry` dict has no `"notes"` key at all -- proving the fix no longer depends on one being present on the slot.

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd plugins/workout && python -m pytest lib/tests/test_generator.py::test_ladder_exercise_notes_update_as_the_program_climbs_rungs -v`
Expected: FAIL -- both weeks show the same (empty, since `entry.get("notes", "")` finds nothing) notes text, not the two different strings.

- [ ] **Step 7: Fix `_build_ladder_exercise` and clean up the now-dead `notes` key**

In `plugins/workout/lib/generator.py`, inside `_build_ladder_exercise`, change:

```python
    for step in weeks:
        result.append(ProgramExercise(
            exercise_id=step["exercise_id"], name=step["name"], movement_pattern=movement_pattern,
            sets=entry["sets"], reps=step["reps"], load=LoadSpec(type="bodyweight", progression_rule=rule),
            tempo=entry["tempo"], rest=entry["rest"], notes=entry.get("notes", ""),
        ))
```

to:

```python
    for step in weeks:
        result.append(ProgramExercise(
            exercise_id=step["exercise_id"], name=step["name"], movement_pattern=movement_pattern,
            sets=entry["sets"], reps=step["reps"], load=LoadSpec(type="bodyweight", progression_rule=rule),
            tempo=entry["tempo"], rest=entry["rest"], notes=step.get("notes", ""),
        ))
```

Then, in `generate_program`, the ladder-slot branch currently builds:

```python
            if ex.get("ladder_group"):
                entry = {"ladder_group": ex["ladder_group"], "sets": DEFAULT_SETS,
                         "weeks_per_rung": DEFAULT_WEEKS_PER_RUNG, "tempo": "2-0-2", "rest": "60s",
                         "notes": ex.get("notes", "")}
                slot_series.append(_build_ladder_exercise(
                    entry, exercises, block_weeks, equipment_profile, constraints))
```

Remove the now-unused `"notes"` key (it is never read by `_build_ladder_exercise` after this fix -- leaving it would be dead, misleading content):

```python
            if ex.get("ladder_group"):
                entry = {"ladder_group": ex["ladder_group"], "sets": DEFAULT_SETS,
                         "weeks_per_rung": DEFAULT_WEEKS_PER_RUNG, "tempo": "2-0-2", "rest": "60s"}
                slot_series.append(_build_ladder_exercise(
                    entry, exercises, block_weeks, equipment_profile, constraints))
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `cd plugins/workout && python -m pytest lib/tests/test_generator.py -v`
Expected: all pass, including the new test.

- [ ] **Step 9: Strip the now-dead static notes from the curated template's ladder slots**

The template's per-slot `"notes"` field is no longer read for ANY ladder slot (the fix above always uses the active rung's own notes instead). Every entry in this template is ladder-based -- all 9 exercise entries across its 3 sessions currently carry static `"notes"` text that becomes dead after this fix, spanning all 5 groups the template uses (`squat_bw`, `push_bw`, `hinge_bw`, `pull_bw`, `core_antiext_bw`). Leaving stale static text in the JSON would misrepresent what actually gets printed.

Replace the full contents of `plugins/workout/references/templates/bodyweight_beginner_3day.json` with (this is Task 1 Step 3's renamed version, with `"notes"` removed from every entry):

```json
{
  "template_id": "bodyweight_beginner_3day",
  "level": "beginner",
  "goal": "general_strength",
  "days_per_week": 3,
  "session_minutes": 30,
  "required_equipment": [],
  "progression_model": "variation-ladder",
  "block_weeks": 8,
  "sessions": [
    {
      "day": 1,
      "label": "Full Body A",
      "exercises": [
        {"ladder_group": "squat_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s"},
        {"ladder_group": "push_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s"},
        {"ladder_group": "core_antiext_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "n/a", "rest": "30s"}
      ]
    },
    {
      "day": 2,
      "label": "Full Body B",
      "exercises": [
        {"ladder_group": "hinge_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s"},
        {"ladder_group": "pull_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s"},
        {"ladder_group": "core_antiext_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "n/a", "rest": "30s"}
      ]
    },
    {
      "day": 3,
      "label": "Full Body C",
      "exercises": [
        {"ladder_group": "squat_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s"},
        {"ladder_group": "push_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s"},
        {"ladder_group": "hinge_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2", "rest": "60s"}
      ]
    }
  ]
}
```

(If Task 1 Step 3's rename hasn't landed yet when you reach this step, apply both changes together -- the file above already reflects `core_bw` renamed to `core_antiext_bw`.)

- [ ] **Step 10: Run the full plugin suite to confirm no regression**

Run: `cd plugins/workout && python -m pytest lib/tests -v`
Expected: all pass. (`_build_loaded_exercise`, the double-progression path, is untouched -- a standalone exercise never changes across weeks, so its static `entry.get("notes", "")` was always correct and stays exactly as-is.)

- [ ] **Step 11: Commit**

```bash
git add plugins/workout/lib/progression.py plugins/workout/lib/generator.py \
    plugins/workout/lib/tests/test_progression.py plugins/workout/lib/tests/test_generator.py \
    plugins/workout/references/templates/bodyweight_beginner_3day.json
git commit -m "fix(workout): ladder exercise notes now come from the active rung, not the slot's original assembly"
```

---

## Task 3: Sub-category bucketing helper

**Files:**
- Modify: `plugins/workout/lib/exercises.py`
- Test: `plugins/workout/lib/tests/test_exercises.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `bucket_by_sub_category(exercises: list) -> dict` -- groups by `sub_category`, falling back to `movement_pattern` when the field is absent or falsy.

- [ ] **Step 1: Write the failing tests**

Add to `plugins/workout/lib/tests/test_exercises.py`:

```python


def test_bucket_by_sub_category_uses_the_tag_when_present():
    exercises = [
        {"exercise_id": "dead_bug", "movement_pattern": "core", "sub_category": "anti_extension"},
        {"exercise_id": "bird_dog", "movement_pattern": "core", "sub_category": "anti_rotation"},
        {"exercise_id": "plank", "movement_pattern": "core", "sub_category": "anti_extension"},
    ]
    buckets = ex_mod.bucket_by_sub_category(exercises)
    assert set(buckets) == {"anti_extension", "anti_rotation"}
    assert {e["exercise_id"] for e in buckets["anti_extension"]} == {"dead_bug", "plank"}
    assert {e["exercise_id"] for e in buckets["anti_rotation"]} == {"bird_dog"}


def test_bucket_by_sub_category_falls_back_to_movement_pattern_when_untagged():
    exercises = [
        {"exercise_id": "box_squat", "movement_pattern": "squat"},
        {"exercise_id": "db_goblet_squat", "movement_pattern": "squat"},
        {"exercise_id": "glute_bridge", "movement_pattern": "hinge"},
    ]
    buckets = ex_mod.bucket_by_sub_category(exercises)
    assert set(buckets) == {"squat", "hinge"}
    assert len(buckets["squat"]) == 2


def test_bucket_by_sub_category_mixes_tagged_and_untagged_within_one_pattern():
    exercises = [
        {"exercise_id": "table_inverted_row", "movement_pattern": "pull", "sub_category": "biceps"},
        {"exercise_id": "db_bent_over_row", "movement_pattern": "pull"},
    ]
    buckets = ex_mod.bucket_by_sub_category(exercises)
    assert set(buckets) == {"biceps", "pull"}


def test_real_core_exercises_span_all_four_sub_categories():
    real = ex_mod.load_exercises()
    core = [e for e in real if e["movement_pattern"] == "core"]
    buckets = ex_mod.bucket_by_sub_category(core)
    assert set(buckets) == {"anti_extension", "anti_rotation", "flexion", "hip_flexor_endurance"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_exercises.py -k bucket_by_sub_category -v`
Expected: FAIL with `AttributeError: module 'exercises' has no attribute 'bucket_by_sub_category'`

- [ ] **Step 3: Implement the helper**

In `plugins/workout/lib/exercises.py`, add after `group_by_pattern`:

```python
def bucket_by_sub_category(exercises: list) -> dict:
    """Group exercises by `sub_category`, falling back to `movement_pattern`
    when the field is absent or falsy. Used by focus-mode session composition
    to find distinct exercise varieties within a focus -- e.g. core's four
    sub-categories, or legs' squat/hinge patterns acting as their own
    buckets since they were never given a finer tag."""
    buckets: dict = {}
    for e in exercises:
        key = e.get("sub_category") or e["movement_pattern"]
        buckets.setdefault(key, []).append(e)
    return buckets
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_exercises.py -v`
Expected: all pass, including the 4 new tests.

- [ ] **Step 5: Commit**

```bash
git add plugins/workout/lib/exercises.py plugins/workout/lib/tests/test_exercises.py
git commit -m "feat(workout): add sub-category bucketing for focus-mode session composition"
```

---

## Task 4: `FOCUS_AREAS` vocabulary and `validate_focus`

**Files:**
- Modify: `plugins/workout/lib/model.py`
- Modify: `plugins/workout/lib/validation.py`
- Test: `plugins/workout/lib/tests/test_validation.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `model.FOCUS_AREAS = ("arms", "core", "legs")` (alphabetical, matching the style of `model.MOVEMENT_PATTERNS`/`model.CONSTRAINT_FLAGS`). `validation.validate_focus(tokens) -> list` -- same contract as `validate_constraints`/`validate_equipment`: returns the tokens unchanged, or raises `TokenError` naming the bad one and the legal set.

- [ ] **Step 1: Add the controlled vocabulary**

In `plugins/workout/lib/model.py`, add alongside the existing constants (after `LEVELS = ("beginner", "intermediate")`):

```python
FOCUS_AREAS = ("arms", "core", "legs")
```

- [ ] **Step 2: Write the failing tests**

Add to `plugins/workout/lib/tests/test_validation.py`:

```python


def test_valid_focus_tokens_pass_through():
    assert validation.validate_focus(["core", "legs", "arms"]) == ["core", "legs", "arms"]


def test_near_miss_focus_is_rejected_not_silently_ignored():
    with pytest.raises(validation.TokenError) as exc:
        validation.validate_focus(["cardio"])
    assert "cardio" in str(exc.value)
    assert "core" in str(exc.value)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_validation.py -k focus -v`
Expected: FAIL with `AttributeError: module 'validation' has no attribute 'validate_focus'`

- [ ] **Step 4: Implement `validate_focus`**

In `plugins/workout/lib/validation.py`, change the import line:

```python
from model import CONSTRAINT_FLAGS
```

to:

```python
from model import CONSTRAINT_FLAGS, FOCUS_AREAS
```

Then add, after `validate_constraints`:

```python
def validate_focus(tokens) -> list:
    """Return the tokens unchanged, or raise TokenError naming the bad one."""
    return _check(tokens, set(FOCUS_AREAS), "focus area")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_validation.py -v`
Expected: all pass, including the 2 new tests.

- [ ] **Step 6: Run the full plugin suite to confirm no regression**

Run: `cd plugins/workout && python -m pytest lib/tests -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add plugins/workout/lib/model.py plugins/workout/lib/validation.py \
    plugins/workout/lib/tests/test_validation.py
git commit -m "feat(workout): add FOCUS_AREAS vocabulary and validate_focus"
```

---

## Task 5: `generate_focus_program`

**Files:**
- Modify: `plugins/workout/lib/generator.py`
- Test: `plugins/workout/lib/tests/test_generator.py`

**Interfaces:**
- Consumes: `exercises_mod.filter_exercises`/`bucket_by_sub_category` (Task 3), `model.FOCUS_AREAS` (Task 4), `_pick_representative`/`_build_ladder_exercise`/`_build_loaded_exercise`/`_reps_from_db` (existing, unchanged).
- Produces: `FOCUS_PATTERNS: dict`, `MINUTES_PER_FOCUS_SLOT: int`, `generate_focus_program(exercises, focus_list, equipment_profile, constraints, level, days_per_week, session_minutes, block_weeks, created) -> Program`.

- [ ] **Step 1: Write the failing tests**

Add to `plugins/workout/lib/tests/test_generator.py`:

```python


FOCUS_EXERCISES = [
    {"exercise_id": "dead_bug", "name": "Dead Bug", "movement_pattern": "core",
     "sub_category": "anti_extension", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_antiext_bw", "ladder_rank": 0, "default_reps": "10-12 / side", "notes": ""},
    {"exercise_id": "plank", "name": "Plank", "movement_pattern": "core",
     "sub_category": "anti_extension", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_antiext_bw", "ladder_rank": 1, "default_reps": "30-45s", "notes": ""},
    {"exercise_id": "bird_dog", "name": "Bird Dog", "movement_pattern": "core",
     "sub_category": "anti_rotation", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_antirot_bw", "ladder_rank": 0, "default_reps": "8-10 / side", "notes": ""},
    {"exercise_id": "curl_up", "name": "Curl-Up", "movement_pattern": "core",
     "sub_category": "flexion", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_flexion_bw", "ladder_rank": 0, "default_reps": "10-12", "notes": ""},
    {"exercise_id": "knee_tuck_hold", "name": "Knee Tuck Hold", "movement_pattern": "core",
     "sub_category": "hip_flexor_endurance", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_hipflexor_bw", "ladder_rank": 0, "default_reps": "15-20s", "notes": ""},
    {"exercise_id": "box_squat", "name": "Box Squat", "movement_pattern": "squat",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
     "ladder_rank": 0, "default_reps": "10-15", "notes": ""},
    {"exercise_id": "glute_bridge", "name": "Glute Bridge", "movement_pattern": "hinge",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "hinge_bw",
     "ladder_rank": 0, "default_reps": "12-15", "notes": ""},
    {"exercise_id": "diamond_pushup", "name": "Diamond Push-Up", "movement_pattern": "push",
     "sub_category": "triceps", "equipment_required": [], "constraint_flags": ["arm-load"],
     "ladder_group": None, "ladder_rank": None, "default_reps": "6-10", "notes": ""},
    {"exercise_id": "table_inverted_row", "name": "Table Inverted Row", "movement_pattern": "pull",
     "sub_category": "biceps", "equipment_required": ["sturdy_table"], "constraint_flags": ["arm-load", "grip"],
     "ladder_group": None, "ladder_rank": None, "default_reps": "8-10", "notes": ""},
    {"exercise_id": "db_bent_over_row", "name": "DB Bent-Over Row", "movement_pattern": "pull",
     "equipment_required": ["dumbbell"], "constraint_flags": ["grip", "arm-load"],
     "ladder_group": None, "ladder_rank": None, "default_reps": "8-12", "notes": ""},
]


def test_focus_program_core_session_has_more_than_one_exercise():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["core"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=3, session_minutes=30, block_weeks=4, created="2026-08-25",
    )
    session = program.weeks[0].sessions[0]
    assert len(session.exercises) > 1
    ids = {ex.exercise_id for ex in session.exercises}
    assert ids <= {"dead_bug", "bird_dog", "curl_up", "knee_tuck_hold"}
    assert model.validate_program(program) == []


def test_focus_program_short_session_still_caps_at_available_sub_categories():
    # 1 minute -> max(2, 0) = 2 wanted, but "legs" here only has squat+hinge
    # eligible (2 buckets) -- this must not somehow invent a 3rd exercise.
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["legs"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=1, session_minutes=1, block_weeks=1, created="2026-08-25",
    )
    assert len(program.weeks[0].sessions[0].exercises) == 2


def test_focus_program_prefers_named_sub_categories_before_generic_pattern_fallback():
    # arms: "triceps" and "biceps" are named sub-categories; the generic
    # "pull" bucket (db_bent_over_row) is a pattern-fallback and must lose
    # the slot when only 2 fit.
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["arms"], equipment_profile=["sturdy_table", "dumbbell"],
        constraints=[], level="beginner", days_per_week=1, session_minutes=14, block_weeks=1,
        created="2026-08-25",
    )
    ids = {ex.exercise_id for ex in program.weeks[0].sessions[0].exercises}
    assert ids == {"diamond_pushup", "table_inverted_row"}


def test_focus_program_cycles_multiple_focuses_across_days():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["core", "legs"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=4, session_minutes=30, block_weeks=1, created="2026-08-25",
    )
    labels = [s.label for s in program.weeks[0].sessions]
    assert labels == ["Core", "Legs", "Core", "Legs"]


def test_focus_program_zero_equipment_arms_is_triceps_only():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["arms"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=1, session_minutes=30, block_weeks=1, created="2026-08-25",
    )
    ids = {ex.exercise_id for ex in program.weeks[0].sessions[0].exercises}
    assert ids == {"diamond_pushup"}  # table_inverted_row needs sturdy_table, unowned


def test_focus_program_meta_reflects_the_split():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["core", "arms"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=2, session_minutes=30, block_weeks=1, created="2026-08-25",
    )
    assert program.meta.source == "generated-focus"
    assert program.meta.goal == "split: core, arms"


def test_focus_program_ladder_exercise_still_progresses_across_the_block():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["core"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=1, session_minutes=8, block_weeks=3, created="2026-08-25",
    )
    # session_minutes=8 -> max(2, 8//7=1) = 2 slots, only anti_extension's
    # ladder is guaranteed to be selected first (alphabetically named).
    week1_ex = next(
        ex for ex in program.weeks[0].sessions[0].exercises
        if ex.movement_pattern == "core" and ex.exercise_id in {"dead_bug", "plank"}
    )
    week3_ex = next(
        ex for ex in program.weeks[2].sessions[0].exercises
        if ex.movement_pattern == "core" and ex.exercise_id in {"dead_bug", "plank"}
    )
    assert week1_ex.exercise_id == "dead_bug"
    assert week3_ex.exercise_id == "plank"


def test_real_exercise_db_builds_a_valid_focus_program_for_every_area():
    exercises = exercises_mod.load_exercises()
    for focus in model.FOCUS_AREAS:
        program = gen_mod.generate_focus_program(
            exercises, focus_list=[focus], equipment_profile=[], constraints=[], level="beginner",
            days_per_week=1, session_minutes=30, block_weeks=2, created="2026-08-25",
        )
        assert model.validate_program(program) == [], focus
        assert program.weeks[0].sessions[0].exercises, focus


def test_full_body_generator_still_produces_a_valid_core_pick_after_the_ladder_split():
    # Regression guard for the core_bw -> 4-group split (see the design
    # spec's "regression risk" section): full-body generation must still
    # deterministically pick exactly one valid core exercise, even though
    # the specific winner changes now that there are 4 rank-0 candidates.
    exercises = exercises_mod.load_exercises()
    program = gen_mod.generate_program(
        exercises, equipment_profile=[], constraints=[], level="beginner",
        days_per_week=1, session_minutes=60, block_weeks=1, created="2026-08-25",
    )
    core_exercises = [
        ex for w in program.weeks for s in w.sessions for ex in s.exercises
        if ex.movement_pattern == "core"
    ]
    assert len(core_exercises) == 1
    assert model.validate_program(program) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_generator.py -k focus_program -v`
Expected: FAIL with `AttributeError: module 'generator' has no attribute 'generate_focus_program'` (the last regression-guard test, `test_full_body_generator_still_produces_a_valid_core_pick_after_the_ladder_split`, should already PASS since it only calls the existing `generate_program` -- confirm this separately: `python -m pytest lib/tests/test_generator.py::test_full_body_generator_still_produces_a_valid_core_pick_after_the_ladder_split -v` should be GREEN already, proving Task 1's data change alone did not break full-body generation.)

- [ ] **Step 3: Implement `generate_focus_program`**

In `plugins/workout/lib/generator.py`, add near the top alongside the other module-level constants (after `MAX_SLOTS = len(PATTERN_ORDER)`):

```python
FOCUS_PATTERNS = {
    "legs": ("squat", "hinge", "carry"),
    "core": ("core",),
    "arms": ("push", "pull"),
}
MINUTES_PER_FOCUS_SLOT = 7
```

Then add these functions after `generate_program` (end of file):

```python
def _focus_slot_count(available: int, session_minutes: int) -> int:
    """How many exercises fill one focused session: the minutes-derived slot
    count (floored at 2), capped by how many distinct sub-category buckets
    are actually available -- never invent a second exercise from a pool of
    one."""
    return min(available, max(2, int(session_minutes) // MINUTES_PER_FOCUS_SLOT))


def _pick_focus_exercises(exercises: list, focus: str, equipment_profile, constraints,
                           session_minutes: int) -> list:
    """The representative exercises for one focused session: one per
    sub-category bucket within the focus's patterns. Named sub-categories
    (e.g. "triceps") sort before pattern-fallback buckets (e.g. a plain
    "push" bucket of untagged compounds), so a short session surfaces the
    focus's dedicated variety before generic filler. Sized by
    session_minutes via `_focus_slot_count`."""
    patterns = FOCUS_PATTERNS[focus]
    eligible = [
        e for e in exercises_mod.filter_exercises(exercises, equipment_profile, constraints)
        if e["movement_pattern"] in patterns
    ]
    buckets = exercises_mod.bucket_by_sub_category(eligible)
    ordered_keys = sorted(buckets, key=lambda k: (k in patterns, k))
    slot_count = _focus_slot_count(len(ordered_keys), session_minutes)
    return [_pick_representative(buckets[key]) for key in ordered_keys[:slot_count]]


def generate_focus_program(exercises: list, focus_list: list, equipment_profile: list,
                            constraints: list, level: str, days_per_week: int,
                            session_minutes: int, block_weeks: int, created: str) -> Program:
    """Build a single-focus split program: each day is assigned one focus
    from `focus_list`, cycling if there are fewer focuses than days. Every
    exercise is picked from a distinct sub-category bucket within that
    focus's patterns (see `_pick_focus_exercises`), so a session is several
    different exercises targeting the same area rather than one exercise
    repeated for the whole block.
    """
    per_slot_weeks = []
    for day in range(1, days_per_week + 1):
        focus = focus_list[(day - 1) % len(focus_list)]
        picks = _pick_focus_exercises(exercises, focus, equipment_profile, constraints, session_minutes)
        slot_series = []
        for ex in picks:
            if ex.get("ladder_group"):
                entry = {"ladder_group": ex["ladder_group"], "sets": DEFAULT_SETS,
                         "weeks_per_rung": DEFAULT_WEEKS_PER_RUNG, "tempo": "2-0-2", "rest": "45s"}
                slot_series.append(_build_ladder_exercise(
                    entry, exercises, block_weeks, equipment_profile, constraints))
            else:
                reps_low, reps_high, reps_suffix = _reps_from_db(ex)
                entry = {"exercise_id": ex["exercise_id"], "sets": DEFAULT_SETS,
                         "reps_low": reps_low, "reps_high": reps_high, "reps_suffix": reps_suffix,
                         "rep_step": DEFAULT_REP_STEP, "load_value": None,
                         "load_increment": DEFAULT_LOAD_INCREMENT, "tempo": "2-0-2", "rest": "45s",
                         "notes": ex.get("notes", "")}
                slot_series.append(_build_loaded_exercise(entry, exercises, block_weeks, "double-progression"))
        per_slot_weeks.append((day, focus.capitalize(), slot_series))

    weeks = []
    for week_number in range(1, block_weeks + 1):
        sessions = []
        for day, label, slot_series in per_slot_weeks:
            week_exercises = [series[week_number - 1] for series in slot_series]
            sessions.append(Session(day=day, label=label, exercises=week_exercises))
        weeks.append(Week(number=week_number, sessions=sessions))

    meta = ProgramMeta(
        level=level, goal=f"split: {', '.join(focus_list)}", days_per_week=days_per_week,
        session_minutes=session_minutes, equipment_profile=list(equipment_profile),
        constraints=list(constraints), created=created, source="generated-focus",
    )
    return Program(
        meta=meta, progression=Progression(model="double-progression", block_weeks=block_weeks), weeks=weeks
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_generator.py -v`
Expected: all pass, including the 9 new tests.

- [ ] **Step 5: Run the full plugin suite to confirm no regression**

Run: `cd plugins/workout && python -m pytest lib/tests -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add plugins/workout/lib/generator.py plugins/workout/lib/tests/test_generator.py
git commit -m "feat(workout): add generate_focus_program for single-focus split routines"
```

---

## Task 6: Wire `--focus` into `program-builder`

**Files:**
- Modify: `plugins/workout/skills/program-builder/scripts/build.py`
- Test: `plugins/workout/lib/tests/test_build_cli.py`

**Interfaces:**
- Consumes: `validation.validate_focus` (Task 4), `generator.generate_focus_program`/`generator.FOCUS_PATTERNS` (Task 5), `model.FOCUS_AREAS` (Task 4).
- Produces: `build()` gains a `focus: list` parameter (default `None`/empty meaning "full-body, unchanged"); `main()` gains a `--focus` CLI argument.

- [ ] **Step 1: Write the failing tests**

Add to `plugins/workout/lib/tests/test_build_cli.py`:

```python


def test_focus_mode_builds_a_split_program(conn):
    program, program_id, notes = build_mod.build(
        "beginner", 3, 30, [], [], 4, conn, focus=["core", "legs", "arms"]
    )
    assert program.meta.source == "generated-focus"
    assert program.meta.goal == "split: core, legs, arms"
    labels = [s.label for s in program.weeks[0].sessions]
    assert labels == ["Core", "Legs", "Arms"]
    assert model.validate_program(program) == []
    assert _saved_exercise_count(conn, program_id) > 0
    assert store.get_program(conn, program_id).meta.source == "generated-focus"
    _renders(program)


def test_focus_mode_skips_template_matching_entirely(conn):
    # Even with dumbbell equipment (which would normally match a curated
    # template), --focus always routes to the generator.
    program, _, notes = build_mod.build(
        "beginner", 3, 40, ["dumbbell"], [], 4, conn, focus=["legs"]
    )
    assert program.meta.source == "generated-focus"
    assert not any("template" in n.lower() for n in notes)


def test_cli_rejects_a_typod_focus_instead_of_ignoring_it(tmp_path, capsys):
    out = tmp_path / "program.md"
    code = build_mod.main([
        "--level", "beginner", "--days", "3", "--minutes", "30",
        "--focus", "cardio", "--out", str(out), "--db", ":memory:",
    ])
    assert code == 2
    assert "cardio" in capsys.readouterr().err
    assert not out.exists()


def test_cli_focus_mode_end_to_end(tmp_path, capsys):
    out = tmp_path / "program.md"
    code = build_mod.main([
        "--level", "beginner", "--days", "3", "--minutes", "20",
        "--focus", "core", "--block-weeks", "4", "--out", str(out), "--db", ":memory:",
    ])
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "Session length: ~20 min" in text or "~20 min" in text
    stdout = capsys.readouterr().out
    assert "Saved as prog_" in stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd plugins/workout && python -m pytest lib/tests/test_build_cli.py -k focus -v`
Expected: FAIL -- `build()` doesn't accept a `focus` keyword argument yet, and `--focus` isn't a recognized CLI flag yet.

- [ ] **Step 3: Wire `--focus` into `build()` and `main()`**

In `plugins/workout/skills/program-builder/scripts/build.py`, add to the imports (already imports `validation`; no new import needed since `generator` is already imported).

Change the `build` function signature and body from:

```python
def build(level: str, days: int, minutes: int, equipment: list, constraints: list, block_weeks, conn):
    """Template ranking -> buildability check -> generator fallback -> validate -> save.

    Returns (program, program_id, notes).
    """
    exercises = exercises_mod.load_exercises()
    all_templates = templates_mod.load_all_templates()
    # `outcome` is the buildability report when a template was chosen, and the
    # reason the best candidate was rejected when none was.
    match, outcome = _choose_template(
        all_templates, exercises, level, days, minutes, equipment, constraints)

    notes = []
    if match is not None:
```

to:

```python
def build(level: str, days: int, minutes: int, equipment: list, constraints: list, block_weeks, conn,
          focus=None):
    """Template ranking -> buildability check -> generator fallback -> validate -> save.

    `focus`, when given, skips template matching entirely (v1 templates are
    all full-body) and builds a single-focus split routine instead, cycling
    across `days` if there are fewer focuses than days.

    Returns (program, program_id, notes).
    """
    exercises = exercises_mod.load_exercises()

    if focus:
        program = generator.generate_focus_program(
            exercises, focus_list=focus, equipment_profile=equipment, constraints=constraints,
            level=level, days_per_week=days, session_minutes=minutes, block_weeks=block_weeks or 8,
            created=dt.date.today().isoformat(),
        )
        notes = [f"Built a {', '.join(focus)} split routine."]
        if not any(s.exercises for w in program.weeks for s in w.sessions):
            raise BuildError(
                "No eligible exercises found for your equipment/constraints in this split. "
                "Loosen a constraint, or run equipment-advisor to see what to buy."
            )
        errors = model.validate_program(program)
        if errors:
            raise ValueError("generated program failed validation: " + "; ".join(errors))
        program_id = store.save_program(conn, program)
        return program, program_id, notes

    all_templates = templates_mod.load_all_templates()
    # `outcome` is the buildability report when a template was chosen, and the
    # reason the best candidate was rejected when none was.
    match, outcome = _choose_template(
        all_templates, exercises, level, days, minutes, equipment, constraints)

    notes = []
    if match is not None:
```

The rest of `build()` (the `else:` branch, the empty-session check, validation, and save at the end) stays exactly as it is -- the new `if focus:` block returns early, before any of that existing code runs.

Now update `main()`. Add the new argument, after the existing `--constraints` line:

```python
    parser.add_argument("--constraints", default="", help="comma-separated constraint flags to avoid")
```

becomes (insert a line after it):

```python
    parser.add_argument("--constraints", default="", help="comma-separated constraint flags to avoid")
    parser.add_argument("--focus", default="",
                         help="comma-separated split focuses (core,legs,arms); cycles across --days. "
                              "When set, skips curated templates entirely.")
```

Then, in the token-validation `try` block, change:

```python
    try:
        equipment = validation.validate_equipment(validation.split_tokens(args.equipment))
        constraints = validation.validate_constraints(validation.split_tokens(args.constraints))
    except validation.TokenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
```

to:

```python
    try:
        equipment = validation.validate_equipment(validation.split_tokens(args.equipment))
        constraints = validation.validate_constraints(validation.split_tokens(args.constraints))
        focus = validation.validate_focus(validation.split_tokens(args.focus))
    except validation.TokenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
```

Finally, pass it through to `build()`. Change:

```python
    conn = store.connect(args.db)
    try:
        program, program_id, notes = build(args.level, args.days, args.minutes, equipment,
                                            constraints, args.block_weeks, conn)
    except BuildError as exc:
```

to:

```python
    conn = store.connect(args.db)
    try:
        program, program_id, notes = build(args.level, args.days, args.minutes, equipment,
                                            constraints, args.block_weeks, conn, focus=focus)
    except BuildError as exc:
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd plugins/workout && python -m pytest lib/tests/test_build_cli.py -v`
Expected: all pass, including the 4 new tests.

- [ ] **Step 5: Run the full plugin suite to confirm no regression**

Run: `cd plugins/workout && python -m pytest lib/tests -v`
Expected: all pass. This is the point to specifically confirm every pre-existing `test_build_cli.py` test (the exhaustive equipment sweep, the runner-up-template test, the session-length tests) still passes unmodified -- `focus` defaults to `None` everywhere it wasn't explicitly passed, so the entire pre-existing call surface is untouched.

- [ ] **Step 6: Commit**

```bash
git add plugins/workout/skills/program-builder/scripts/build.py \
    plugins/workout/lib/tests/test_build_cli.py
git commit -m "feat(workout): add --focus flag to program-builder for split routines"
```

---

## Task 7: Document `--focus` in `program-builder`'s SKILL.md

**Files:**
- Modify: `plugins/workout/skills/program-builder/SKILL.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing consumed by other tasks.

- [ ] **Step 1: Read the current file**

Read `plugins/workout/skills/program-builder/SKILL.md` in full before editing, since exact current wording (and whether it still says `skills/program-builder/scripts/build.py` vs. `${CLAUDE_PLUGIN_ROOT}/...`) needs to be matched, not guessed.

- [ ] **Step 2: Add a focus-mode section**

In the `## Workflow` section, after the existing steps that describe building a full-body program, add a new numbered step (renumber subsequent steps if needed) documenting `--focus`:

```markdown
N. **Split-routine mode.** If the user asks for a single-focus session (a
   "core day," "leg day," "arm day") rather than a full-body program, or
   explicitly wants a split routine across several days ("a core day, a leg
   day, and an arm day, each on different days"), pass `--focus` instead of
   letting the tool pick a template:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/program-builder/scripts/build.py \
       --level beginner --days 6 --minutes 25 \
       --focus core,legs,arms \
       --block-weeks 4 --format markdown --out program.md
   ```
   `--focus` takes a comma-separated list from `core`, `legs`, `arms`, and
   cycles across `--days` (3 focuses over 6 days repeats the list twice; a
   single focus with `--days 3` repeats that one focus every day). When
   `--focus` is set, curated templates are skipped entirely -- every session
   is assembled from the eligible exercise pool, sized to fit `--minutes`,
   picking a different exercise per distinct sub-category within the focus
   (e.g. a core day pulls from anti-extension, anti-rotation, flexion, and
   hip-flexor-endurance work, not one exercise repeated for the whole block).

   **Tell the user up front if their arm day will be thin.** True bodyweight
   bicep isolation barely exists -- a zero-equipment `arms` focus is
   triceps-only (diamond push-up, pike push-up). The biceps pick (table
   inverted row) needs a sturdy table; a triceps dip variation needs a
   chair. If the user hasn't run `equipment-intake`, ask about a chair/table
   specifically before promising a well-rounded arm day.
```

- [ ] **Step 3: Verify the edit renders correctly**

Run: `python -c "print(open('plugins/workout/skills/program-builder/SKILL.md').read())"` and read through it once to confirm the new section reads naturally alongside the existing content, uses the same `${CLAUDE_PLUGIN_ROOT}` convention as the rest of the file, and didn't duplicate or renumber anything incorrectly.

- [ ] **Step 4: Commit**

```bash
git add plugins/workout/skills/program-builder/SKILL.md
git commit -m "docs(workout): document --focus split-routine mode in program-builder"
```

---

## Task 8: Full-suite verification and manual smoke test

**Files:** none modified -- verification only.

**Interfaces:**
- Consumes: everything built in Tasks 1-7.
- Produces: nothing new.

- [ ] **Step 1: Run the full test suite**

Run: `cd plugins/workout && python -m pytest lib/tests -v`
Expected: every test passes. Note the new total count for your own record (was 126 before this plan; expect roughly 126 + 1 (progression notes) + 1 (ladder exercise notes) + 4 (bucketing) + 2 (validate_focus) + 9 (generate_focus_program) + 4 (build.py --focus) = 147).

- [ ] **Step 2: Manual end-to-end smoke test -- the original failing scenario**

This is the exact request that surfaced both bugs this plan fixes: a no-equipment core routine, starting low, working up over a month.

```bash
cd plugins/workout
python skills/equipment-intake/scripts/intake.py --set "" --db /tmp/focus-smoke/w.db
python skills/program-builder/scripts/build.py \
    --level beginner --days 3 --minutes 20 --equipment "" --constraints "" \
    --focus core --block-weeks 4 --format markdown --out /tmp/focus-smoke/core.md \
    --db /tmp/focus-smoke/w.db
python -c "print(open('/tmp/focus-smoke/core.md', encoding='utf-8').read())"
```

Expected: the command exits 0, prints `Saved as prog_...`, and the markdown shows a real 4-week core-focused program with 2+ distinct core exercises per session (not one exercise repeated), climbing ladders across the weeks with each rung's own correct notes text (not frozen on week-1's exercise).

- [ ] **Step 3: Manual end-to-end smoke test -- the split routine across different days**

```bash
python skills/program-builder/scripts/build.py \
    --level beginner --days 6 --minutes 25 --equipment sturdy_table,chair \
    --focus core,legs,arms --block-weeks 4 --format markdown --out /tmp/focus-smoke/split.md \
    --db /tmp/focus-smoke/w.db
python -c "print(open('/tmp/focus-smoke/split.md', encoding='utf-8').read()[:2000])"
```

Expected: 6 sessions labeled Core/Legs/Arms/Core/Legs/Arms, arms day includes both the triceps and biceps picks (chair + table both owned), legs day includes squat and hinge work.

- [ ] **Step 4: Manual smoke test -- typo'd focus is rejected loudly**

```bash
python skills/program-builder/scripts/build.py \
    --level beginner --days 3 --minutes 20 --focus cor \
    --out /tmp/focus-smoke/bad.md --db /tmp/focus-smoke/w.db
echo "exit: $?"
```

Expected: `error: unknown focus area 'cor'. Valid focus areas: arms, core, legs`, exit code 2, no output file written.

- [ ] **Step 5: Confirm full-body mode is unaffected**

```bash
python skills/program-builder/scripts/build.py \
    --level beginner --days 3 --minutes 40 --equipment dumbbell \
    --block-weeks 4 --format markdown --out /tmp/focus-smoke/fullbody.md \
    --db /tmp/focus-smoke/w.db
```

Expected: `Used curated template: dumbbell_beginner_3day` -- identical behavior to before this plan (no `--focus` passed).

- [ ] **Step 6: Validate the plugin manifest is still intact**

Run: `python -c "import json; json.load(open('plugins/workout/.claude-plugin/plugin.json')); print('OK')"`
Expected: `OK` (this plan didn't touch the manifest, but confirm nothing else broke it).

No commit for this task -- it's verification only. If any step fails, that's a real bug in an earlier task; go back and fix it there (with a new commit on that task's area), then re-run this task's steps from Step 1.

---

## Post-plan: what's deliberately deferred

- No curated templates for focus mode (`--focus` always uses the generator).
- No focus categories beyond `core`, `legs`, `arms`.
- No multiple exercises per sub-category in one session.
- SQLite schema, storage, and rendering are completely unchanged -- focus-mode programs are ordinary `Program` objects.
