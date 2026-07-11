---
name: analyze-rentals
version: 0.1.0
description: End-to-end rental analysis for 2-4 unit multifamily. Takes a Redfin CSV export, ingests and filters to 2-4 unit, screens with a zero-API heuristic, PAUSES for the user to prune the shortlist, then spends RentCast calls only on survivors and produces a ranked markdown + CSV report of cash-on-cash returns across price scenarios. Use when the user says "analyze these rentals", "run the rental pipeline", or hands over a Redfin CSV of multifamily listings.
allowed-tools:
  - Bash
  - Read
---

# analyze-rentals

Orchestrates the full pipeline. **The human review gate between screening and RentCast
enrichment is mandatory** — never spend API calls before the user prunes.

## Preconditions

Check config exists:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --show-path
```
If `"exists": false`, run `/setup` first (see setup SKILL.md), then continue.

## Pipeline

Use a temp working directory for intermediate JSON.

1. **Ingest** the Redfin CSV:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/ingest-listings/scripts/ingest.py "$CSV" > "$TMP/props.json"
   ```
2. **Screen** (zero API):
   ```bash
   cat "$TMP/props.json" | python3 ${CLAUDE_PLUGIN_ROOT}/skills/screen-deals/scripts/screen.py > "$TMP/screened.json"
   ```
3. **HUMAN GATE.** Present the ranked shortlist from `screened.json` (address, price,
   heuristic rent, asking cash-on-cash, max offer). Ask the user which to keep. Write the
   kept subset to `$TMP/pruned.json`. Do not proceed until they answer.
4. **Enrich** only the pruned set (metered — one RentCast call each):
   ```bash
   cat "$TMP/pruned.json" | python3 ${CLAUDE_PLUGIN_ROOT}/skills/enrich-rents/scripts/enrich.py > "$TMP/enriched.json"
   ```
   If it exits 4 (quota), tell the user how many were enriched and offer to continue with
   the partial set or resume next cycle.
5. **Report**:
   ```bash
   cat "$TMP/enriched.json" | python3 ${CLAUDE_PLUGIN_ROOT}/skills/report/scripts/report.py --out-dir .
   ```
6. Summarize the top results in chat and point the user to `rental-report.md` /
   `rental-report.csv`. Flag any property whose report notes mention thin/absent comps.

## Guardrails

- Never skip the human gate.
- Never print the RentCast API key.
- If ingest reports 0 kept rows, the Redfin search probably was not filtered to
  "Multi-family (2-4 Unit)" — tell the user to re-export.
