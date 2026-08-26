---
name: program-builder
version: 0.1.0
description: Build a progressive, printable home-strength program from a curated template or generated from the eligible exercise pool, tailored to the user's equipment and any physical constraints. Use when the user asks for a workout program, wants to start training again "from near nothing," or wants to remix/regenerate their current program.
allowed-tools:
  - Bash
  - Read
triggers:
  - build me a workout program
  - give me a strength program
  - i want to start working out
  - remix my program
  - regenerate my program
---

# program-builder

Orchestrator. Turns (level, equipment, days/week, session length, active
constraints) into a full multi-week `Program`, persists it to SQLite, and
renders a printable output.

## Workflow

1. **Gather inputs conversationally:**
   - Level: `beginner` or `intermediate` (default `beginner` if the user
     describes starting from near nothing).
   - Days per week and session length in minutes.
   - Equipment: read from the saved profile
     (`equipment-intake`'s `--show`) unless the user wants to plan around a
     hypothetical/different set.
   - Constraints: any injury/physical limitation to design around, expressed
     as constraint flags -- `grip`, `arm-load`, `overhead`, `spinal-load`,
     `impact` (e.g. bilateral elbow tendinosis -> `grip,arm-load`).
   - Block length: how many weeks (default 8 if not specified).
   - Output format: `markdown` (default, printable tracker), `csv`
     (printable log grid), or `json` (interchange/backup).

2. **Build and render:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/program-builder/scripts/build.py \
       --level beginner --days 3 --minutes 30 \
       --equipment dumbbell,pull_up_bar \
       --constraints grip,arm-load \
       --block-weeks 8 --format markdown --out program.md
   ```
   The script prints which curated template it used, or explains why it fell
   back to generating one (missing equipment, the closest template conflicts
   with the stated constraints, its sessions are longer than the time the
   user has, or it would train some movement pattern without putting any of
   the user's equipment to work when something they own could) -- relay
   that explanation to the user so they understand where their program came
   from. Every qualifying template is tried in order, so a rejected top pick
   falls through to the next curated template before the generator. It also
   prints any movement-pattern slot that had to be dropped for lack of
   eligible exercises, and the saved `program_id` (`Saved as prog_...`),
   which is how the program is looked up again in the local store.

   `--minutes` sizes a *generated* session. A curated template is fixed
   content, so it keeps its own session length and the script says so when
   that differs from the request -- the printed "~N min" is always the
   program's real length, never a relabelled one.

   Unknown constraint flags or equipment ids exit non-zero with the legal set
   printed -- fix the token and re-run rather than dropping it, or the
   program will silently ignore a real constraint.

3. **Split-routine mode.** If the user asks for a single-focus session (a
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

4. **Deliver the output.** For `markdown`, offer to also produce it as an
   HTML artifact (styled, printable) via the `Artifact` tool -- follow the
   `artifact-design` skill's guidance when doing so. For `csv`, the file is
   meant to be printed and filled in by hand.

5. **Remix:** if the user doesn't like the result, re-run step 2 with a
   different equipment/constraint combination, or pass `--format json` and
   hand-edit specific exercises, then re-render with `render.py`'s functions
   (`lib/render.py`) for a quick one-off adjustment.

## Notes

- The output's `log` fields are intentionally blank in v1 -- this is a
  one-shot printable plan, not an adaptive one. See `lib/model.py`'s `log`
  field and the plugin design spec for the future adaptive/phone-logging
  direction.
- Every generated program is grounded in `references/sources.md` -- if the
  user asks "why is it built this way," look up the relevant `informs` tag
  there.
- A short `--minutes` request (roughly under the curated templates' own
  session length) routes even a zero-equipment user to the generator instead
  of the bodyweight template. The generated fallback still progresses each
  slot through its full variation ladder week to week -- it isn't a static
  program -- but it loses the template's day-to-day pattern rotation. Mention
  this if a "start from nothing" user asks for a notably short session.
