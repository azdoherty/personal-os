"""Parse a Redfin CSV export into normalized Property objects, keeping only
2-4 unit multifamily rows (the plugin's scope).

Redfin's 'Download All' export uses a stable header. We validate that the columns
we depend on are present and error clearly (naming the missing ones) rather than
silently producing garbage.
"""
from __future__ import annotations

import csv
import io

from lib.models import Property

MULTIFAMILY_2_4 = "Multi-Family (2-4 Unit)"

REQUIRED_COLUMNS = [
    "PROPERTY TYPE", "ADDRESS", "CITY", "STATE OR PROVINCE",
    "ZIP OR POSTAL CODE", "PRICE",
]


class SchemaError(Exception):
    pass


def _num(row: dict, key: str) -> float | None:
    raw = (row.get(key) or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int(row: dict, key: str) -> int | None:
    v = _num(row, key)
    return int(v) if v is not None else None


def parse_redfin_csv(text: str) -> tuple[list[Property], dict]:
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise SchemaError(
            "Redfin CSV is missing required columns: " + ", ".join(missing)
            + ". Re-export via Redfin's 'Download All' button."
        )

    props: list[Property] = []
    total = dropped_type = 0
    for row in reader:
        total += 1
        if (row.get("PROPERTY TYPE") or "").strip() != MULTIFAMILY_2_4:
            dropped_type += 1
            continue
        props.append(Property(
            address=(row.get("ADDRESS") or "").strip(),
            city=(row.get("CITY") or "").strip(),
            state=(row.get("STATE OR PROVINCE") or "").strip(),
            zip=(row.get("ZIP OR POSTAL CODE") or "").strip(),
            list_price=_num(row, "PRICE") or 0.0,
            property_type=MULTIFAMILY_2_4,
            beds=_num(row, "BEDS"),
            baths=_num(row, "BATHS"),
            sqft=_num(row, "SQUARE FEET"),
            year_built=_int(row, "YEAR BUILT"),
            lot_size=_num(row, "LOT SIZE"),
            hoa_monthly=_num(row, "HOA/MONTH") or 0.0,
            latitude=_num(row, "LATITUDE"),
            longitude=_num(row, "LONGITUDE"),
            url=(row.get("URL") or "").strip(),
            mls=(row.get("MLS#") or "").strip(),
            days_on_market=_int(row, "DAYS ON MARKET"),
        ))
    stats = {"total": total, "kept": len(props), "dropped_type": dropped_type}
    return props, stats
