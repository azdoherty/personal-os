"""Filter scored dealers and rank by total delivered cost for an order size."""
from __future__ import annotations

from datetime import date

from lib.models import dealer_key, normalize_name
from lib.reputation import days_old


def tier_price(tiers: dict, gallons: float) -> tuple[int, float] | None:
    """Price for the largest volume tier the order qualifies for."""
    eligible = [(int(t), p) for t, p in tiers.items() if int(t) <= gallons]
    if not eligible:
        return None
    return max(eligible)


def _listed(entry: dict, names: list[str]) -> bool:
    wanted = {normalize_name(n) for n in names}
    return normalize_name(entry["dealer"]) in wanted or entry.get("key") in names


def rank(entries: list[dict], gallons: float, min_score: float, max_age_days: int,
         allowlist: list[str] = (), blocklist: list[str] = (),
         today: date | None = None) -> dict:
    """entries: scored quote dicts (Quote.to_dict() + 'reputation').
    Returns {'ranked': [...], 'excluded': [...]} each sorted by total cost."""
    ranked, excluded = [], []
    for e in entries:
        e = dict(e)
        e.setdefault("key", dealer_key(e["dealer"], e.get("phone", "")))
        tp = tier_price(e["tiers"], gallons)
        if tp:
            e["tier"], e["price_per_gal"] = tp
            e["total"] = round(tp[1] * gallons + (e.get("fee") or 0), 2)
        rep = e.get("reputation") or {}
        age = days_old(e.get("updated"), today)
        e["age_days"] = age
        reason = None
        if _listed(e, list(blocklist)):
            reason = "on your blocklist"
        elif not tp:
            reason = f"no price tier for {gallons:g} gal (min tier {min(int(t) for t in e['tiers'])})"
        elif e.get("min_delivery_gallons") and gallons < e["min_delivery_gallons"]:
            reason = f"minimum delivery {e['min_delivery_gallons']} gal"
        elif age is not None and age > max_age_days:
            reason = f"price is {age} days old"
        elif _listed(e, list(allowlist)):
            e["allowlisted"] = True
        elif rep.get("score", 0) < min_score:
            reason = f"reputation {rep.get('score', 0):g} < {min_score:g} ({rep.get('verdict', 'unscored')})"
        if reason:
            e["excluded_reason"] = reason
            excluded.append(e)
        else:
            ranked.append(e)
    key = lambda e: (e.get("total", float("inf")), -(e.get("reputation") or {}).get("score", 0))
    return {"ranked": sorted(ranked, key=key), "excluded": sorted(excluded, key=key)}
