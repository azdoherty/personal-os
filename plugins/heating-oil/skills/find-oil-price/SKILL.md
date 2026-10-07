---
name: find-oil-price
version: 0.1.0
description: Find the cheapest home heating oil (#2 fuel / kerosene) delivered to the user's ZIP from reputable dealers. Scrapes COD dealer price listings, researches each cheap dealer's reputation (Google reviews, BBB, years in business, complaints) with WebSearch, scores it 0-100, and ranks the dealers that pass by total delivered cost for the order size. Use for "cheapest heating oil near me", "who should I order oil from", or "is $X/gal a good oil price".
triggers:
  - heating oil price
  - cheapest heating oil
  - oil delivery near me
  - COD oil dealer
allowed-tools:
  - Bash
  - WebSearch
  - WebFetch
---

# find-oil-price

Pipeline: **fetch → research reputation → score → rank**. Scripts are stdlib-only and
talk JSON over stdin/stdout. `S=${CLAUDE_PLUGIN_ROOT}/skills/find-oil-price/scripts`.

## 0. Config

If `python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --show-path` reports
`"exists": false`, run the `setup` skill first. Do the same if the user mentions a
different ZIP. For a one-off, pass `--zip` and the source flags directly instead.

## 1. Fetch prices

```bash
python3 $S/fetch.py > /tmp/oil-quotes.json            # uses configured sources
python3 $S/fetch.py --zone NH:2 > ...   # or explicit sources
```

Each source fails on its own with a warning on stderr. If the result is empty or very
thin (fewer than ~4 dealers), or the ZIP is outside New England, gather quotes yourself:
WebSearch "heating oil prices <town> <state>" / "COD heating oil <ZIP>". WebFetch the
dealer-listing and dealer pages you find. Write what you collect as a JSON list and
merge it in:

```json
[{"dealer": "Blue Flame Energy", "town": "Stratham", "phone": "603-555-0199",
  "tiers": {"100": 3.50, "150": 3.31}, "updated": "2026-10-05",
  "url": "https://...", "source": "blueflame.example", "fee": 0, "min_delivery_gallons": 100}]
```
```bash
python3 $S/fetch.py --manual manual.json > /tmp/oil-quotes.json   # add --zone/--url to combine
```
Only include prices you actually saw, with the date the page shows. Never estimate a price.

## 2. Research reputation (you, with WebSearch)

List the cheapest dealers that have no cached research (the cache is kept 30 days):
```bash
python3 $S/score.py --todo 8 < /tmp/oil-quotes.json
```
For each one, search on its own for: `"<dealer>" <town> reviews`,
`"<dealer>" BBB`, and `"<dealer>" complaint OR lawsuit OR "attorney general"`.
Record only what you actually found, keyed by the `key` from `--todo`:

```json
{"6035550199": {"google_rating": 4.5, "google_reviews": 120, "bbb_grade": "A",
                "bbb_accredited": false, "years_in_business": 15, "complaint_hits": 0,
                "notes": "Family-owned since 2011; reviews praise on-time delivery"}}
```
- Leave out any field you couldn't find. It scores a neutral 50, so a dealer you didn't
  research ends up `inconclusive` instead of falsely `reputable`.
- `complaint_hits`: count credible, specific reports, such as AG actions, lawsuits, a
  pattern of short deliveries, prepay/contract defaults, or bad fuel. Don't count a single
  angry review. Use `0` only if you searched and found nothing.

## 3. Score and rank

```bash
python3 $S/score.py --reputation rep.json --save-cache < /tmp/oil-quotes.json \
  | python3 $S/rank.py --benchmark 3.62
```
- `--benchmark`: optionally look up the state's latest weekly residential heating oil
  average (EIA, or the state energy office's weekly survey) with WebSearch and pass it in.
- Overrides: `--gallons`, `--min-score`, `--max-age-days`, `--format json`.

Weights live in `references/reputation-weights.json`: Google reviews 0.30, BBB 0.25,
integrity 0.20, years 0.15, cross-site corroboration + price freshness 0.10. Verdicts:
≥70 reputable, 40–69 inconclusive, <40 avoid.

## 4. Report

Show the markdown table. Lead with the best dealer and its phone number. Say why the
cheaper dealers were excluded. Remind the user to confirm price, fees, and payment
method when they call, because COD prices change daily. If the top results are
`inconclusive (unresearched)`, research them before you recommend one.
