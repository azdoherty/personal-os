---
name: equipment-intake
version: 0.1.0
description: Record what home-gym equipment the user owns (and re-run whenever gear changes) so program-builder and equipment-advisor know what's available. Use when the user first sets up the workout plugin, or says things like "I just got a pull-up bar" or "update my equipment."
allowed-tools:
  - Bash
triggers:
  - what equipment do i have
  - update my equipment
  - i got a
  - set up my home gym
---

# equipment-intake

Collects a normalized equipment profile and saves it to the local SQLite store
(`lib/store.py`). This profile drives both `program-builder` (what exercises
are eligible) and `equipment-advisor` (what's worth buying next).

## Workflow

1. **Show the checklist.** Run:
   ```bash
   python3 skills/equipment-intake/scripts/intake.py --list
   ```
   Present the equipment as a grouped checklist to the user (bodyweight is
   always available; ask about bands, dumbbells, kettlebells, barbell+rack,
   bench, pull-up bar, weighted vest, sled, belt squat rig, sturdy table).

2. **Save the profile** once the user has answered:
   ```bash
   python3 skills/equipment-intake/scripts/intake.py --set dumbbell,pull_up_bar,sled
   ```

3. **Confirm** by showing it back:
   ```bash
   python3 skills/equipment-intake/scripts/intake.py --show
   ```

Re-run step 2 any time the user acquires or gets rid of equipment -- it fully
replaces the saved profile (it's not additive).

## Notes

- Equipment ids must match `references/equipment.json` -- use `--list` rather
  than guessing ids.
- This skill only stores *what's owned*. Physical constraints (e.g. "avoid
  grip-heavy exercises") are collected by `program-builder` at build time,
  not here -- they can change per-program while equipment ownership is
  durable.
