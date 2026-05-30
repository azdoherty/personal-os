#!/usr/bin/env python3
"""refresh_recall_corpus: pull CPSC recall data into a local corpus for fast brand lookup.

CPSC publishes a free REST API:
  https://www.saferproducts.gov/RestWebServices/Recall?format=json&RecallDateStart=YYYY-MM-DD&RecallDateEnd=YYYY-MM-DD

Each call returns up to 5000 recalls. We fetch year-by-year for the last N
years, normalize into a slim record per recall, and write a single JSON
file the brand-check script can grep through.

Output schema (per record):
  {
    "recall_id": <int>,
    "date": "YYYY-MM-DD",
    "title": "...",
    "url": "https://www.cpsc.gov/...",
    "search_blob": "<lower-cased text of brand-relevant fields concatenated>",
    "hazards": ["burn", "fire", ...],
    "injuries": <int>,
    "products": ["Name 1", "Name 2"]
  }

Usage:
  refresh_recall_corpus.py [--years N] [--out PATH]
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

CPSC_BASE = "https://www.saferproducts.gov/RestWebServices/Recall"
USER_AGENT = "claude-code-research-plugin/0.4 corpus-refresh"

DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "references", "recall_corpus.json",
)


def fetch_year(year: int) -> list[dict]:
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    url = f"{CPSC_BASE}?format=json&RecallDateStart={start}&RecallDateEnd={end}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    return data if isinstance(data, list) else []


def _names(items: list[dict] | None, field: str = "Name") -> list[str]:
    if not items:
        return []
    return [str(it.get(field) or "").strip() for it in items if it.get(field)]


def normalize(recall: dict) -> dict:
    products = _names(recall.get("Products"), "Name")
    manufacturers = _names(recall.get("Manufacturers"), "Name")
    retailers = _names(recall.get("Retailers"), "Name")
    distributors = _names(recall.get("Distributors"), "Name")
    importers = _names(recall.get("Importers"), "Name")
    hazards = _names(recall.get("Hazards"), "Name")
    injuries = recall.get("Injuries") or []
    injury_count = sum(int(i.get("Quantity", 0) or 0) for i in injuries if isinstance(i, dict))

    title = (recall.get("Title") or "").strip()
    sold_at = (recall.get("SoldAtLabel") or "").strip()
    contact = (recall.get("ConsumerContact") or "").strip()

    blob_parts = [title, sold_at, contact] + products + manufacturers + retailers + distributors + importers
    blob = " | ".join(p for p in blob_parts if p).lower()

    raw_date = recall.get("RecallDate") or ""
    date = raw_date.split("T", 1)[0] if "T" in raw_date else raw_date[:10]

    return {
        "recall_id": recall.get("RecallID"),
        "date": date,
        "title": title,
        "url": recall.get("URL") or "",
        "search_blob": blob,
        "hazards": hazards,
        "injuries": injury_count,
        "products": products,
        "manufacturers": manufacturers,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Refresh local CPSC recall corpus.")
    p.add_argument("--years", type=int, default=5, help="How many years back to fetch (default 5).")
    p.add_argument("--out", default=DEFAULT_OUT, help="Output JSON path.")
    args = p.parse_args()

    current_year = datetime.now(timezone.utc).year
    years = list(range(current_year - args.years + 1, current_year + 1))

    all_records: list[dict] = []
    errors: list[str] = []
    for y in years:
        try:
            print(f"fetching {y}...", file=sys.stderr)
            recalls = fetch_year(y)
            all_records.extend(normalize(r) for r in recalls)
            time.sleep(0.5)  # be polite
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, json.JSONDecodeError) as e:
            errors.append(f"{y}: {e}")

    all_records.sort(key=lambda r: r.get("date") or "", reverse=True)

    payload = {
        "source": "CPSC SaferProducts REST API",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "years_covered": years,
        "record_count": len(all_records),
        "errors": errors or None,
        "records": all_records,
    }
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(all_records)} recalls to {args.out}", file=sys.stderr)
    if errors:
        print(f"errors: {errors}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
