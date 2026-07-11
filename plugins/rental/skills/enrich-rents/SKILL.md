---
name: enrich-rents
version: 0.1.0
description: Enrich a PRUNED shortlist of 2-4 unit properties with real RentCast rent estimates and rental comps. Metered — spends one RentCast API call per property (free tier is 50/month), so only run this on the properties the user kept after screen-deals. Reads Property[] JSON on stdin, writes enriched Property[] JSON. Caches responses to avoid re-spending.
allowed-tools:
  - Bash
---

# enrich-rents

Replaces the screening heuristic rent with a real RentCast estimate + comps, for the
properties the user kept at the review gate.

## Cost

One billable RentCast call per uncached property (`/avm/rent/long-term` returns rent +
comps together). Free tier is 50 calls/month. Responses cache to `rentcast.cache.json`
in the working directory, so reruns within a cycle do not re-spend.

## Invoke (only on the pruned list)

```bash
cat pruned.json | python3 ${CLAUDE_PLUGIN_ROOT}/skills/enrich-rents/scripts/enrich.py > enriched.json
```

If the quota is exhausted mid-run the script stops, emits what it has, notes the rest as
un-enriched, and exits 4. Report that to the user rather than silently dropping properties.
