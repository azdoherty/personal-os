---
name: ingest-listings
version: 0.1.0
description: Parse a Redfin CSV export ("Download All") into normalized 2-4 unit multifamily property JSON. Use when the user has a Redfin CSV of local for-sale listings and wants to start the rental-analysis pipeline, or asks to load/ingest listings. Drops everything that is not "Multi-Family (2-4 Unit)".
allowed-tools:
  - Bash
---

# ingest-listings

Turns a Redfin CSV export into the normalized `Property[]` JSON every other rental
skill consumes. Keeps only `PROPERTY TYPE == "Multi-Family (2-4 Unit)"` rows.

## First run

If `~/.config/personal-os/rental/config.json` (or `%APPDATA%\personal-os\rental\config.json`)
does not exist, tell the user to run `/setup` first.

## How to invoke

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ingest-listings/scripts/ingest.py path/to/redfin.csv
```

Stdout is a JSON array of properties; stderr reports how many rows were kept vs dropped.

## Normalized schema

Each item is a `Property`: `address, city, state, zip, list_price, property_type, beds,
baths, sqft, year_built, lot_size, hoa_monthly, latitude, longitude, url, mls,
days_on_market, num_units, units[], gross_monthly_rent, rent_source, tax_annual,
insurance_annual, rehab, comps[], notes[]`. Fields not present in the CSV are null/empty
until a later stage fills them.
