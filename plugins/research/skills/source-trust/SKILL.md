---
name: source-trust
version: 0.1.0
description: Score web sources 0-100 for trustworthiness using domain prior, recency, engagement, and cross-source corroboration. Use whenever you have a list of search results (from reddit-search, forum-search, web-search) and need to rank them by reliability before summarizing. Usually called internally by /literature-review.
allowed-tools:
  - Bash
  - Read
triggers:
  - score these sources
  - rank by trust
  - evaluate source quality
---

# source-trust

Take a flat array of source items and add `trust` (0-100) + `trust_reasons` to each. Pure function — no network calls.

## When to use

- After fanning out across `/reddit-search`, `/forum-search`, `/web-search`. Combine the results into one JSON array and pipe through this skill.
- Anytime you need a defensible ranking of mixed-quality sources.

## How to invoke

Pipe a JSON array (the concatenated output of source skills) into the script:

```bash
cat all_sources.json | python3 ${CLAUDE_PLUGIN_ROOT}/skills/source-trust/scripts/score.py
```

The script reads from stdin and writes the same items back with two new fields, sorted descending by `trust`.

## Scoring model

| Component | Range | Logic |
|---|---|---|
| Domain prior | 0–100 (default 40) | Looked up in `references/domain-trust.json`. Subdomains fall back to parent domain. |
| Recency | x0.5 – x1.0 multiplier | 100% at ≤ 6 months, linear decay to 50% by 3 years. Applied around the neutral center of 40 so trusted-but-old sources don't crash below the default. |
| Engagement | +0 – +15 | Log-scaled bonus from `score + num_comments`. Null counts (e.g. Reddit RSS) give 0 — neutral, not penalized. |
| Corroboration | +0 or +10 | +10 if ≥3 of the item's content keywords also appear in ≥2 other sources. Boosts claims that multiple independent sources mention. |

Final score: `clip(0, 100, centered_prior + engagement + corroboration)`.

## Tuning

Edit `references/domain-trust.json` to adjust priors. Edit the constants at the top of `score.py` to change recency curves, engagement bonuses, or corroboration thresholds. The trust map is loaded fresh on every invocation.

## Output

Same input array, each item augmented with:

```json
{
  "trust": 78,
  "trust_reasons": [
    "prior 78 (domain=stackoverflow.com)",
    "recency x0.92 (140d old)",
    "engagement +8 (score=412, comments=37)",
    "corroboration +10 (corroborated terms: [...])"
  ]
}
```

Output is sorted descending by `trust`.

## Failure modes

- **Input not a JSON array:** the script errors with exit 2 and a message on stderr.
- **Empty array:** returns `[]` and exits 0.
- **Missing `references/domain-trust.json`:** all items get the default prior of 40. Not fatal.
