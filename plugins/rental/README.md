# rental

Analyze local **2–4 unit multifamily** listings for long-term rental investment.

## Pipeline

1. `/setup` — one-time: write your market, financing, and expense assumptions to your OS config dir.
2. Export your local for-sale search from Redfin ("Download All" → CSV). Filter the Redfin search to "Multi-family (2-4 Unit)".
3. `/analyze-rentals path/to/redfin.csv` — ingest → heuristic screen → **you prune the shortlist** → RentCast enrichment → markdown + CSV report.

Individual stages are also available: `/ingest-listings`, `/screen-deals`, `/enrich-rents`, `/report`.

## Data sources

- **Redfin CSV export** — free, unlimited local inventory (manual download).
- **RentCast API** — rent estimates + comps + valuations. Free tier is 50 calls/month; the pipeline spends calls only on the shortlist you approve.

## Requirements

- Python 3.10+ (stdlib only).
- A free RentCast API key (https://rentcast.io) for the enrichment step.

## Metrics

Cash-on-cash, cap rate, and NOI are computed per the standard definitions (capex excluded
from NOI, subtracted from cash flow as a reserve). See
`docs/superpowers/specs/2026-07-11-rental-investment-plugin-design.md` for the full model.
