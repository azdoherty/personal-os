"""Quotes gathered by hand, by phone, or by Claude via WebSearch/WebFetch.

Input: a JSON list of objects, each with `dealer` and either `price` (+ optional
`min_gallons`) or `tiers` ({"100": 3.49, "150": 3.39}); optional `town`, `phone`,
`url`, `updated`, `fee`, `min_delivery_gallons`, `source`.
"""
from __future__ import annotations

from lib.models import Quote


def parse_manual(items: list[dict], default_source: str = "manual") -> list[Quote]:
    out = []
    for d in items:
        q = Quote.from_dict(d)
        if not q.sources:
            q.sources = [default_source]
        out.append(q)
    return out
