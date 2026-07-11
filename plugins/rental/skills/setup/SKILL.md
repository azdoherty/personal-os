---
name: setup
version: 0.1.0
description: One-time interactive setup for the rental plugin. Prompts for your market (city + ZIPs), RentCast API key, financing assumptions (down payment, term, closing costs, rate spread), expense defaults, deal thresholds, and screening rent heuristic, then writes them to your OS config dir (never the repo). Use the first time any rental skill runs and no config exists, or when the user asks to change their rental assumptions.
allowed-tools:
  - Bash
---

# setup

Writes the rental plugin's config to your OS config dir
(`%APPDATA%\personal-os\rental\config.json` on Windows,
`~/.config/personal-os/rental/config.json` otherwise). Never committed to the repo.

## When to run

- The first time a rental skill runs and `setup.py --show-path` reports `"exists": false`.
- Whenever the user wants to change assumptions.

## Procedure

1. Check the path/existence:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --show-path
   ```
2. Ask the user for (defaults come from `references/expense-defaults.json`, so only
   `market` and `rentcast_api_key` are strictly required — offer the documented defaults
   for the rest and let them adjust):
   - **Market**: city/label + list of ZIP codes to hunt in.
   - **RentCast API key**: free key from rentcast.io. Paste it; it is stored locally only.
   - **Financing**: down payment %, loan term, closing cost %, investment-rate spread,
     optional pinned rate.
   - **Expenses**: vacancy %, maintenance %, capex %, management %, insurance/yr,
     landlord-paid utilities/mo, property-tax fallback %.
   - **Thresholds**: target cash-on-cash %, min monthly cash flow, 1% rule on/off.
   - **Screening rent**: `per_sqft` (rent per sqft) or `per_bedroom` (rent by bedroom count).
3. Build a JSON object with the user's answers and pipe it to `--write`:
   ```bash
   echo '{"market":{"label":"...","zips":["..."]},"rentcast_api_key":"...", ...}' \
     | python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --write
   ```
4. Confirm the write succeeded. Do NOT print the API key back to the user.
