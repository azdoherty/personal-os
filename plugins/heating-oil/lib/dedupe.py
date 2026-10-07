"""Merge the same dealer seen on multiple sources into one Quote."""
from __future__ import annotations

from lib.models import Quote, dealer_key, normalize_name, phone_digits


def merge_quotes(quotes: list[Quote]) -> list[Quote]:
    """Group by phone number, falling back to normalized name. A name match also
    joins a phone-keyed group, so a listing without a phone still merges."""
    groups: dict[str, Quote] = {}
    name_to_key: dict[str, str] = {}
    for q in quotes:
        name = normalize_name(q.dealer)
        key = phone_digits(q.phone) or name_to_key.get(name) or name
        name_to_key.setdefault(name, key)
        cur = groups.get(key)
        if cur is None:
            groups[key] = Quote(**{**q.__dict__, "tiers": dict(q.tiers),
                                   "sources": list(q.sources)})
            continue
        for tier, price in q.tiers.items():
            if tier not in cur.tiers or price < cur.tiers[tier]:
                cur.tiers[tier] = price
        cur.sources = sorted(set(cur.sources) | set(q.sources))
        if q.updated and (not cur.updated or q.updated > cur.updated):
            cur.updated = q.updated
        for attr in ("town", "phone", "url"):
            if not getattr(cur, attr) and getattr(q, attr):
                setattr(cur, attr, getattr(q, attr))
        cur.fee = max(cur.fee, q.fee)
        if q.min_delivery_gallons:
            cur.min_delivery_gallons = max(cur.min_delivery_gallons or 0, q.min_delivery_gallons)
    return list(groups.values())


def source_count(q: Quote) -> int:
    """Distinct source sites (zones of the same site count once)."""
    return len({s.split(":")[0] for s in q.sources})


__all__ = ["merge_quotes", "source_count", "dealer_key"]
