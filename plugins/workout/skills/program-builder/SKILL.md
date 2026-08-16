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
   python3 skills/program-builder/scripts/build.py \
       --level beginner --days 3 --minutes 30 \
       --equipment dumbbell,pull_up_bar \
       --constraints grip,arm-load \
       --block-weeks 8 --format markdown --out program.md
   ```
   The script prints which curated template it used, or explains why it fell
   back to generating one (missing equipment, or the closest template
   conflicts with the stated constraints) -- relay that explanation to the
   user so they understand where their program came from.

3. **Deliver the output.** For `markdown`, offer to also produce it as an
   HTML artifact (styled, printable) via the `Artifact` tool -- follow the
   `artifact-design` skill's guidance when doing so. For `csv`, the file is
   meant to be printed and filled in by hand.

4. **Remix:** if the user doesn't like the result, re-run step 2 with a
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
