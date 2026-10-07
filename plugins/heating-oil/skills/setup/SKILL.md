---
name: setup
version: 0.1.0
description: One-time setup for the heating-oil plugin. Records your ZIP, typical order size (gallons), minimum dealer reputation, price sources (newenglandoil.com zone(s) and/or dealer-listing URLs), and dealer allow/blocklists in your OS config dir (never the repo). Use the first time find-oil-price runs with no config, or when the user wants to change their ZIP, order size, or sources.
allowed-tools:
  - Bash
  - WebSearch
  - WebFetch
---

# setup

Writes `~/.config/personal-os/heating-oil/config.json`
(`%APPDATA%\personal-os\heating-oil\config.json` on Windows; override with
`HEATING_OIL_CONFIG`). The dealer reputation cache lives next to it.

## Procedure

1. Check whether config exists:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --show-path
   ```
2. Ask the user for:
   - **ZIP** (required, 5 digits).
   - **Gallons** per order (default 150; many dealers price 150+ gal lower than 100–149).
   - **Minimum reputation score** (default 70 = "reputable"; 40 admits "inconclusive").
   - **Max price age** in days (default 7).
   - **Allowlist / blocklist**: dealers they already trust or refuse to use (names or phone numbers).
3. Pick sources:
   - **New England ZIP** (MA, RI, NH, ME, VT, CT): newenglandoil.com lists COD dealer prices by
     state zone. Look at the state's page (e.g. `https://www.newenglandoil.com/newhampshire/`)
     with WebFetch to find which zone(s) list towns near the ZIP. Include adjacent zones if the
     user is near a boundary. Record them as `{"state": "NH", "zone": 10}`.
   - **Any ZIP**: add `sources.urls` for any page that shows a dealer price table (the parser
     reads the table headers, so most COD dealer listing sites work). Check with
     `fetch.py --url <url>` that dealers come back.
   - Outside New England with no listing site: leave sources empty. `find-oil-price` will
     gather quotes with WebSearch and pass them in with `--manual`.
4. Write it:
   ```bash
   echo '{"zip":"03801","gallons":150,"min_score":70,
          "sources":{"newenglandoil_zones":[{"state":"NH","zone":10}],"urls":[]},
          "allowlist":[],"blocklist":[]}' \
     | python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --write
   ```
   `--show` prints the merged config (defaults come from `references/defaults.json`).
