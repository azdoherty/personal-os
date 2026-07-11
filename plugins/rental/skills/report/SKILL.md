---
name: report
version: 0.1.0
description: Render a ranked markdown report plus a CSV export from enriched 2-4 unit property JSON. Re-underwrites each property with its real rent and the live mortgage rate, producing per-property cash-on-cash scenario tables (asking / -5% / -10%) and the max offer price to hit your target return. Use as the final step of the rental pipeline. Reads Property[] JSON on stdin.
allowed-tools:
  - Bash
---

# report

Final stage. Reads enriched `Property[]` JSON, re-underwrites with real rents + the live
rate, and writes `rental-report.md` and `rental-report.csv`.

## Invoke

```bash
cat enriched.json | python3 ${CLAUDE_PLUGIN_ROOT}/skills/report/scripts/report.py --out-dir .
```

- `--strict-cashflow` drops the capex reserve from cash flow (pure textbook figure).

The markdown has a headline ranking table then one section per property with a
scenario table (price, P&I, NOI, cap rate, cash flow, cash-on-cash, meets-target flag)
and the max offer price. The CSV has one row per property for sorting in a spreadsheet.
