# Design: `rental` plugin — long-term multifamily rental analysis

**Date:** 2026-07-11
**Status:** Approved (brainstorming), pending implementation plan
**Marketplace:** `personal-os`

## Goal

Help the user start investing in **2–4 unit long-term rental properties** in their local
market by turning raw for-sale inventory into a ranked, underwritten shortlist. The end
goal is diversifying income. The plugin pulls local listings, estimates rent from comps,
and reports cash-on-cash return across price scenarios so the user knows what to offer.

Scope is deliberately narrow: **2–4 unit residential multifamily only.** No single-family
(user wants multiple-renter stability), no condos (unless buying a whole complex, which is
out of budget), no 5+ unit commercial (different financing/valuation).

## Key constraint: data sources (2026)

Neither Zillow nor Redfin offers an official listings API to individuals. Zillow moved to
enterprise-only Bridge Interactive ($500+/mo, industry affiliation required); Redfin has no
public API. The chosen approach is a **hybrid**:

- **Redfin CSV export** — Redfin's site "Download All" button exports search results to
  CSV. Free, unlimited, no ToS violation. Supplies the raw for-sale inventory. Manual step.
- **RentCast API** — the practical choice for solo developers. Free tier: 50 calls/mo, no
  credit card. Supplies rent estimates, rental comps, AVM valuations, and market stats.
  Spent **only on the post-review shortlist** to conserve calls. Paid tiers (~$74/mo) if
  the user outgrows it.

Scraping Zillow/Redfin was rejected (fragile + against ToS).

## Architecture

Composable single-purpose skills + one orchestrator (mirrors the existing `research`
plugin), **but the real logic lives in a shared, unit-tested `lib/` package** and the skill
scripts are thin CLI wrappers. Stdlib-only Python (no pip), per marketplace convention.

```
plugins/rental/
  .claude-plugin/plugin.json
  README.md
  lib/                        # reusable, unit-tested core
    __init__.py
    models.py                 # dataclasses: Property, Unit, Assumptions, DealResult, Scenario
    config.py                 # locate/load/validate/merge config; path + env resolution
    listings.py               # Redfin CSV -> normalized Property[] (filter to 2-4 unit)
    rentcast.py               # RentCast client: rent estimate, rental comps, AVM, listings
    rates.py                  # live benchmark rate (FRED MORTGAGE30US) + investment spread
    underwrite.py             # THE engine: expenses -> cash flow -> cash-on-cash scenarios
    screen.py                 # cheap heuristic underwrite + threshold filter + rank
    report.py                 # render markdown + CSV from DealResult[]
  skills/
    setup/            SKILL.md + scripts/setup.py
    ingest-listings/  SKILL.md + scripts/ingest.py
    screen-deals/     SKILL.md + scripts/screen.py
    enrich-rents/     SKILL.md + scripts/enrich.py
    report/           SKILL.md + scripts/report.py
    analyze-rentals/  SKILL.md          # orchestrator (prose + calls the scripts)
  references/
    expense-defaults.json     # documented, editable default assumption rates
  tests/
    test_underwrite.py  test_listings.py  test_screen.py  test_config.py
```

Every stage reads/writes normalized JSON on stdin/stdout (same discipline as `research`),
so any single stage can be rerun or piped. `underwrite.py` is **pure functions over
dataclasses** — no I/O, no network — making it trivially testable and reusable by both
`screen` (heuristic mode) and the final RentCast-fed pass.

### Scripts importing `lib/`

No `pip install`. Skill scripts resolve the plugin root via `CLAUDE_PLUGIN_ROOT` (fallback:
walk up from `__file__`) and `sys.path.insert(0, <plugin_root>)`, then `import lib.xxx`.
This is a new pattern for the marketplace (the `research` plugin uses subprocess calls
between skills); it is justified here because the underwrite math is pure shared logic that
belongs in one tested place, not duplicated across scripts.

## Config & secrets

The repo is **public**, so config must live outside the repo and never be committed.
Resolved by `config.py`, with a `RENTAL_CONFIG` env override:

- Windows: `%APPDATA%\personal-os\rental\config.json`
- macOS/Linux: `~/.config/personal-os/rental/config.json`

`.gitignore` also gets `config.local.json` and `*.cache.json` as belt-and-suspenders.
`references/expense-defaults.json` (committed) holds the documented defaults `setup` copies.

**First-run detection:** every skill and the orchestrator check for config on startup; if
missing, they route the user into `setup` before doing anything else. Automatic the first
time, never nagging afterward.

```jsonc
{
  "market": { "label": "Springfield, IL", "zips": ["62701", "62704"] },
  "rentcast_api_key": "...",              // sent as X-Api-Key header, never in URL
  "financing": {
    "down_payment_pct": 0.25,             // typical for 2-4 unit non-owner-occ
    "loan_term_years": 30,
    "closing_cost_pct": 0.03,
    "rate_spread_pct": 0.0075,            // added to live benchmark
    "rate_pin_pct": null                  // set to a number to override live fetch
  },
  "expenses": {
    "vacancy_pct": 0.05,                  // % of gross rent
    "maintenance_pct": 0.08,
    "capex_pct": 0.05,
    "management_pct": 0.08,
    "insurance_annual": 1800,             // $ or null -> derive from RentCast
    "landlord_paid_utilities_monthly": 100,
    "property_tax_pct_fallback": 0.02     // used only if no tax record found
  },
  "thresholds": {
    "target_coc_pct": 0.08,               // flagged in scenario table + used to pre-filter
    "min_monthly_cashflow": 100,
    "use_one_percent_rule": false
  },
  "screening": {
    "heuristic_rent_mode": "per_sqft",    // "per_sqft" | "per_bedroom"
    "rent_per_sqft": 1.10,                // seeded at setup, refined over time
    "rent_per_bedroom": { "1": 850, "2": 1150, "3": 1450 }
  },
  "scenarios": { "price_offsets": [0.0, -0.05, -0.10] }
}
```

## The underwrite engine (`lib/underwrite.py`)

Pure functions over dataclasses. Math verified against the literature (NOI/cap-rate/CoC
definitions from JPMorgan, Wall Street Prep, PropertyMetrics, Griffin Funding, LoopNet).

**1. Effective mortgage rate** (`rates.py`)

```
benchmark      = latest MORTGAGE30US from FRED weekly CSV (no API key)
effective_rate = rate_pin_pct  if set  else  benchmark + rate_spread_pct
```

**2. Financing**

```
loan          = price * (1 - down_payment_pct)
monthly_PI    = loan * r(1+r)^n / ((1+r)^n - 1)     # r = effective_rate/12, n = term*12
cash_invested = price * down_payment_pct
              + price * closing_cost_pct
              + rehab                                # optional per-property input, default 0
```

**3. Income & expenses (monthly)**

```
gross_rent = sum of per-unit rents
vacancy    = gross_rent * vacancy_pct
EGI        = gross_rent - vacancy
operating_expenses =                                # NO capex, NO mortgage
      maintenance_pct*gross_rent + management_pct*gross_rent
    + taxes_monthly            # from RentCast/listing tax record, else price*tax_fallback/12
    + insurance_monthly        # config value, or RentCast-derived
    + landlord_paid_utilities_monthly
```

**4. Returns**

```
NOI            = (EGI - operating_expenses) * 12    # excludes capex AND debt service
cap_rate       = NOI / price
annual_debt_service = monthly_PI * 12
capex_reserve       = capex_pct * gross_rent * 12
annual_cashflow = NOI - annual_debt_service - capex_reserve
cash_on_cash    = annual_cashflow / cash_invested
```

**Capex treatment (disclosed modeling choice):** capex is excluded from NOI/cap rate
(literature-strict — capex is a capital cost, not operating, so cap rates stay
financing/ownership-neutral and comparable). A capex **reserve** is still subtracted from
cash flow, because the buy-and-hold investor genuinely sets that money aside. A
`--strict-cashflow` flag drops the reserve from cash flow too, for the pure textbook figure.

**5. Scenario table.** Recompute a row for each `price_offsets` entry (asking, -5%, -10%),
**plus one derived row**: the max offer price where `cash_on_cash == target_coc_pct`, solved
directly (CoC is monotonic in price — no search needed). That row is the "bid at this
number" figure; any scenario meeting target is flagged.

**Deliberate omissions (YAGNI):** no PMI (2-4 unit investment loans require >=20-25% down,
so it never applies); no rent/appreciation growth projection (cash-on-cash is a year-1
metric). Both are easy to add later as a multi-year pro forma.

## Data flow (orchestrator: `analyze-rentals`)

```
[first-run? -> setup]
   |
1. ingest-listings   Redfin CSV -> normalized Property[] (filter to 2-4 unit)   [no API]
   |
2. screen-deals      heuristic rent (config, zero API) -> underwrite ->         [no API]
   |                 threshold filter -> rank by heuristic cash-on-cash
   |
   *** HUMAN GATE ***  present ranked shortlist; user manually prunes / writes off
   |
3. enrich-rents      RentCast on survivors ONLY: per-unit rent estimate,        [metered]
   |                 rental comps, AVM, tax/insurance where available
   |
4. (underwrite)      re-run engine with real rents + live rate -> scenarios     [no API]
   |
5. report            ranked markdown report (per-property scenario tables) + CSV export
```

The human gate is both a cost control (RentCast calls only after pruning) and a sanity
check. Screening uses a **zero-API config heuristic** for rent so that *no* API calls happen
before the user reviews the list — honoring the user's explicit request.

## Skill contracts

| Skill | Input | Output | API |
|---|---|---|---|
| `setup` | interactive prompts | writes `config.json` to OS config dir | none |
| `ingest-listings` | path to Redfin CSV | normalized `Property[]` JSON | none |
| `screen-deals` | `Property[]` JSON + config | ranked `DealResult[]` (heuristic) JSON | none |
| `enrich-rents` | pruned `Property[]` JSON + config | `Property[]` with real rents/comps JSON | RentCast |
| `report` | `DealResult[]` JSON | markdown report + CSV file | none |
| `analyze-rentals` | Redfin CSV path | end-to-end run with human gate | RentCast |

Normalized shapes live in `lib/models.py` and are documented in the `ingest-listings`
SKILL.md (the way `research` documents its schema in `reddit-search`).

## Output

- **Markdown report** — ranked shortlist, one section per property with its price/return
  scenario table, key assumptions, and caveats (comp thinness, missing tax record, etc.).
- **CSV export** — one row per property with all computed metrics, for sorting/tracking in
  a spreadsheet.

## Error handling & edge cases

- **No config** -> route to `setup` (first-run detection).
- **RentCast free-tier exhausted / 429** -> stop before spending, report how many analyzed
  vs remaining, suggest re-running next cycle or upgrading. Never silently drop properties.
- **FRED rate fetch fails** -> fall back to `rate_pin_pct` if set, else last cached
  benchmark, else a clearly-labeled hardcoded default; surface which was used.
- **Redfin CSV schema drift** -> `listings.py` validates expected columns, errors with the
  missing column names rather than producing garbage.
- **Property not 2-4 unit / unit count unknown** -> excluded at ingest with a count of how
  many were dropped and why.
- **Thin/absent rental comps** -> flag low confidence in the report; do not hide it.
- **Missing tax record** -> fall back to `property_tax_pct_fallback`, labeled as an estimate.
- **RentCast caching** -> responses cached to `*.cache.json` (gitignored) keyed by
  property/ZIP so reruns within a cycle don't re-spend calls.

## Testing

No live-API tests (matches `research`). Focus on the pure core:

- `test_underwrite.py` — worked examples with hand-checked NOI, cap rate, cash-on-cash,
  monthly P&I, the solved max-offer-price row, and `--strict-cashflow` behavior.
- `test_listings.py` — Redfin CSV parsing, 2-4 unit filtering, schema-drift errors.
- `test_screen.py` — heuristic rent modes, threshold filtering, ranking order.
- `test_config.py` — path resolution per-OS, env override, validation of missing/bad fields.

RentCast and FRED clients are exercised with recorded/sample JSON fixtures, not live calls.

## Open items for the implementation plan

- Confirm exact Redfin CSV column names against a real export (unit count is the critical
  field and Redfin's CSV may not expose it directly — may need to infer from
  property-type/beds, which affects the ingest filter).
- Confirm RentCast endpoint shapes for rent estimate + rental comps + AVM and their exact
  free-tier call accounting (one call per property vs per endpoint).
- Decide the `expense-defaults.json` starting values (documented, user-tunable).
