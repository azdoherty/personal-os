# heating-oil

Finds the cheapest home heating oil delivered to your ZIP from **reputable** dealers.

```
fetch.py  ──quotes──▶  score.py  ──scored──▶  rank.py  ──▶ markdown / JSON
(newenglandoil zones,     ▲ reputation signals          (order size, tiers, fees,
 any dealer-table URL,    │ from WebSearch,              freshness, min score,
 manual quotes)           │ cached 30 days               allow/blocklist)
```

- **Sources**: newenglandoil.com zone pages (MA/RI/NH/ME/VT/CT), any URL with a dealer
  price table (the parser maps columns by header text, so most layouts work), and manual
  quotes that Claude collects with WebSearch/WebFetch or that you take down over the phone.
  The same dealer seen on more than one site is merged by phone number or name.
- **Reputation** (0–100): Google rating weighted by review count, BBB grade and
  accreditation, years in business, complaints/AG actions, plus cross-site corroboration
  and how fresh the price is. Missing signals score a neutral 50.
- **Ranking**: uses the right volume tier (e.g. 150+ gal), adds flat fees, drops stale
  prices, dealers below your minimum delivery, and dealers below the reputation threshold.
  It also lists the cheaper dealers it excluded and why.

Config and the dealer cache live in `~/.config/personal-os/heating-oil/` (never the repo).

```bash
# one-off, no config
S=plugins/heating-oil/skills/find-oil-price/scripts
python3 $S/fetch.py --zip 03801 --zone NH:10 | python3 $S/score.py | python3 $S/rank.py --gallons 150
```
Unresearched dealers come out `inconclusive`. Run it through the `find-oil-price` skill
so Claude does the reputation research.

Tests: `cd plugins/heating-oil && python -m pytest -v`. Parsers are tested against
representative HTML fixtures. If a live site changes its layout, save the page into
`tests/fixtures/` and add a case.
