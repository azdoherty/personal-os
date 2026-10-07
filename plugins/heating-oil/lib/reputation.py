"""Dealer reputation score (0-100) from signals Claude gathers via WebSearch.

Signals per dealer (all optional; a missing signal scores a neutral 50):
  google_rating (1-5), google_reviews (count), bbb_grade ("A+".."F", "NR"),
  bbb_accredited (bool), years_in_business (number), complaint_hits (count of
  credible complaints / AG actions / lawsuits / fuel-quality or short-delivery
  reports found; 0 means "searched, found nothing").
Corroboration (listed on 2+ sites) and price freshness come from the quote.
"""
from __future__ import annotations

import math
from datetime import date

from lib.config import load_reference
from lib.dedupe import source_count
from lib.models import Quote

NEUTRAL = 50.0


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def google_score(rating, reviews) -> float:
    if rating is None:
        return NEUTRAL
    quality = _clip((float(rating) - 3.0) / 2.0 * 100)        # 3.0 -> 0, 5.0 -> 100
    confidence = min(1.0, math.log10((reviews or 0) + 1) / math.log10(201))  # 200 reviews = full
    return NEUTRAL + (quality - NEUTRAL) * confidence


def bbb_score(grade, accredited, grades: dict) -> float:
    if grade is None and accredited is None:
        return NEUTRAL
    base = grades.get(str(grade).upper().strip(), NEUTRAL) if grade else NEUTRAL
    return _clip(base + (10 if accredited else 0))


def years_score(years) -> float:
    if years is None:
        return NEUTRAL
    return _clip(float(years) * 5)                              # 20 years = 100


def integrity_score(hits) -> float:
    if hits is None:
        return NEUTRAL
    return _clip(100 - 35 * int(hits))


def days_old(updated: str | None, today: date | None = None) -> int | None:
    if not updated:
        return None
    return ((today or date.today()) - date.fromisoformat(updated)).days


def corroboration_freshness_score(q: Quote, today: date | None = None) -> float:
    corr = 100.0 if source_count(q) >= 2 else NEUTRAL
    age = days_old(q.updated, today)
    if age is None:
        fresh = 40.0
    elif age <= 2:
        fresh = 100.0
    elif age <= 7:
        fresh = 70.0
    else:
        fresh = 20.0
    return (corr + fresh) / 2


def score_dealer(q: Quote, signals: dict | None, today: date | None = None,
                 ref: dict | None = None) -> dict:
    ref = ref or load_reference("reputation-weights.json")
    s = signals or {}
    parts = {
        "google_reviews": google_score(s.get("google_rating"), s.get("google_reviews")),
        "bbb": bbb_score(s.get("bbb_grade"), s.get("bbb_accredited"), ref["bbb_grades"]),
        "years_in_business": years_score(s.get("years_in_business")),
        "integrity": integrity_score(s.get("complaint_hits")),
        "corroboration_freshness": corroboration_freshness_score(q, today),
    }
    w = ref["weights"]
    total = round(sum(parts[k] * w[k] for k in w), 1)
    th = ref["thresholds"]
    verdict = ("reputable" if total >= th["reputable"]
               else "inconclusive" if total >= th["inconclusive"] else "avoid")
    researched = any(s.get(k) is not None for k in
                     ("google_rating", "bbb_grade", "years_in_business", "complaint_hits"))
    return {"score": total, "verdict": verdict, "signals": {k: round(v, 1) for k, v in parts.items()},
            "researched": researched, "notes": s.get("notes", "")}
