---
name: screen-deals
version: 0.1.0
description: Screen normalized 2-4 unit property JSON with a zero-API rent heuristic, underwrite each, filter by your configured thresholds, and rank by cash-on-cash. Use after ingest-listings and BEFORE spending any RentCast calls, so the user can review and prune the shortlist. Reads Property[] JSON on stdin, writes ranked DealResult[] JSON.
allowed-tools:
  - Bash
---

# screen-deals

Zero-API screening. Estimates rent from config heuristics (no network), underwrites every
property, keeps those meeting your thresholds, and ranks by cash-on-cash.

## Invoke

```bash
cat properties.json | python3 ${CLAUDE_PLUGIN_ROOT}/skills/screen-deals/scripts/screen.py
```

## IMPORTANT: human review gate

After running this, **present the ranked shortlist to the user and let them prune it**
before any RentCast enrichment. Screening spends no API calls; enrichment does. Pass only
the properties the user keeps to `/enrich-rents`.
