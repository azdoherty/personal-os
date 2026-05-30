#!/usr/bin/env python3
"""review-pattern: analyze a corpus of reviews for fake-review red flags.

Operates on review text supplied by the orchestrator. Without paid scraping
infrastructure we cannot pull Amazon reviews directly, so the input must be
prepared upstream — pasted by the user, copied from a public listing, or
gathered via a scraping skill.

Input (stdin) — either:
  (a) JSON array of review objects:
      [{"text": "...", "rating": 5, "date": "2024-01-01",
        "verified": true, "reviewer": "...", "incentivized": false}, ...]
      All fields except "text" are optional.
  (b) Plain text with reviews separated by blank lines (no metadata).

Output (stdout): JSON with authenticity score 0-100 and red-flag breakdown.

Signals (each 0-100, higher = more trustworthy):
  rating_distribution    — penalizes 95%+ 5-star concentration
  template_language      — penalizes generic-marketing phrase frequency
  vocabulary_diversity   — penalizes type-token ratio too low (repetition)
  ngram_overlap          — penalizes near-duplicate review pairs
  incentivized_disclosure — penalizes Vine / "free product" disclosures
  verified_purchase      — credits high verified ratio (if data present)
  burst_pattern          — penalizes if dates are unnaturally clustered

Verdict: ≥70 trustworthy, 40–69 mixed, <40 suspicious.
"""

import argparse
import collections
import json
import math
import re
import sys
from datetime import datetime

# ---- Templates / red-flag phrases ---------------------------------------

GENERIC_TEMPLATES = (
    "highly recommend", "love this product", "love this", "works great",
    "exactly what i needed", "five stars", "5 stars", "best purchase",
    "great product", "amazing product", "perfect for", "great quality",
    "easy to use", "as advertised", "as described", "very happy with",
    "no complaints", "would buy again", "great value", "must have",
    "game changer", "life changer", "highly satisfied",
)
INCENTIVE_PHRASES = (
    "received this product", "in exchange for", "free product",
    "discounted product", "discounted price", "honest review",
    "for testing", "vine program", "amazon vine", "i was given",
    "for an unbiased", "for a review", "complimentary product",
)


def load_input() -> list[dict]:
    raw = sys.stdin.read().strip()
    if not raw:
        return []
    if raw.lstrip().startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [r if isinstance(r, dict) else {"text": str(r)} for r in data]
        except json.JSONDecodeError:
            pass
    # plain text — split on blank lines
    blocks = re.split(r"\n\s*\n", raw)
    return [{"text": b.strip()} for b in blocks if b.strip()]


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z']{1,}", (text or "").lower())


# ---- Signals -------------------------------------------------------------

def rating_distribution(reviews: list[dict]) -> dict:
    ratings = [r.get("rating") for r in reviews if isinstance(r.get("rating"), (int, float))]
    if not ratings:
        return {"name": "rating_distribution", "weight": 0.15, "score": 50,
                "note": "no rating data — neutral", "details": None}
    n = len(ratings)
    five_star_ratio = sum(1 for r in ratings if r >= 4.5) / n
    one_star_ratio = sum(1 for r in ratings if r <= 1.5) / n
    if five_star_ratio >= 0.95:
        score, note = 10, f"{five_star_ratio:.0%} 5-star concentration (extreme)"
    elif five_star_ratio >= 0.85:
        score, note = 40, f"{five_star_ratio:.0%} 5-star concentration (high)"
    elif five_star_ratio >= 0.70:
        score, note = 70, f"{five_star_ratio:.0%} 5-star — normal for good products"
    else:
        score, note = 100, f"healthy spread ({five_star_ratio:.0%} 5-star, {one_star_ratio:.0%} 1-star)"
    return {
        "name": "rating_distribution",
        "weight": 0.15,
        "score": score,
        "note": note,
        "details": {
            "count": n,
            "mean": round(sum(ratings) / n, 2),
            "five_star_ratio": round(five_star_ratio, 3),
            "one_star_ratio": round(one_star_ratio, 3),
        },
    }


def template_language(reviews: list[dict]) -> dict:
    texts_lc = [(r.get("text") or "").lower() for r in reviews]
    if not texts_lc:
        return {"name": "template_language", "weight": 0.20, "score": 50,
                "note": "no review text — neutral", "details": None}
    template_hits: dict[str, int] = {}
    flagged_reviews = 0
    for t in texts_lc:
        hit_any = False
        for phrase in GENERIC_TEMPLATES:
            if phrase in t:
                template_hits[phrase] = template_hits.get(phrase, 0) + 1
                hit_any = True
        if hit_any:
            flagged_reviews += 1
    ratio = flagged_reviews / len(texts_lc)
    if ratio >= 0.80:
        score, note = 10, f"{ratio:.0%} of reviews use generic marketing templates"
    elif ratio >= 0.60:
        score, note = 35, f"{ratio:.0%} of reviews use generic marketing templates"
    elif ratio >= 0.40:
        score, note = 60, f"{ratio:.0%} of reviews use generic phrases"
    else:
        score, note = 100, f"low template language ({ratio:.0%})"
    top = sorted(template_hits.items(), key=lambda kv: -kv[1])[:5]
    return {
        "name": "template_language",
        "weight": 0.20,
        "score": score,
        "note": note,
        "details": {"flagged_ratio": round(ratio, 3), "top_templates": top},
    }


def vocabulary_diversity(reviews: list[dict]) -> dict:
    all_tokens: list[str] = []
    for r in reviews:
        all_tokens.extend(tokens(r.get("text", "")))
    if len(all_tokens) < 50:
        return {"name": "vocabulary_diversity", "weight": 0.15, "score": 50,
                "note": "too few words to analyze — neutral", "details": None}
    ttr = len(set(all_tokens)) / len(all_tokens)
    if ttr >= 0.55:
        score, note = 100, f"diverse vocabulary (TTR={ttr:.2f})"
    elif ttr >= 0.40:
        score, note = 75, f"moderate vocabulary (TTR={ttr:.2f})"
    elif ttr >= 0.25:
        score, note = 45, f"low vocabulary diversity (TTR={ttr:.2f})"
    else:
        score, note = 15, f"very low vocabulary (TTR={ttr:.2f}) — likely templated"
    return {
        "name": "vocabulary_diversity",
        "weight": 0.15,
        "score": score,
        "note": note,
        "details": {"type_token_ratio": round(ttr, 3),
                    "total_tokens": len(all_tokens),
                    "unique_tokens": len(set(all_tokens))},
    }


def ngram_overlap(reviews: list[dict]) -> dict:
    """Detect near-duplicate review pairs via 4-gram Jaccard."""
    texts = [(r.get("text") or "").lower() for r in reviews if (r.get("text") or "")]
    if len(texts) < 3:
        return {"name": "ngram_overlap", "weight": 0.20, "score": 50,
                "note": "too few reviews to compare — neutral", "details": None}

    def ngrams(text: str, n: int = 4) -> set:
        toks = tokens(text)
        return {" ".join(toks[i:i+n]) for i in range(len(toks) - n + 1)} if len(toks) >= n else set()

    sets = [ngrams(t) for t in texts]
    duplicates = []
    for i in range(len(sets)):
        if not sets[i]:
            continue
        for j in range(i + 1, len(sets)):
            if not sets[j]:
                continue
            inter = len(sets[i] & sets[j])
            union = len(sets[i] | sets[j])
            if union == 0:
                continue
            jaccard = inter / union
            if jaccard >= 0.30:
                duplicates.append({"i": i, "j": j, "jaccard": round(jaccard, 3)})
    pair_count = len(sets) * (len(sets) - 1) / 2
    dup_ratio = len(duplicates) / pair_count if pair_count else 0
    if dup_ratio >= 0.15:
        score, note = 0, f"{dup_ratio:.0%} of review pairs near-duplicate — likely copy-paste"
    elif dup_ratio >= 0.05:
        score, note = 30, f"{dup_ratio:.0%} of review pairs near-duplicate"
    elif dup_ratio > 0:
        score, note = 70, f"{dup_ratio:.0%} of review pairs share substantial wording"
    else:
        score, note = 100, "no near-duplicate review pairs"
    return {
        "name": "ngram_overlap",
        "weight": 0.20,
        "score": score,
        "note": note,
        "details": {"duplicate_pairs": duplicates[:10], "total_pairs": int(pair_count)},
    }


def incentivized_disclosure(reviews: list[dict]) -> dict:
    texts_lc = [(r.get("text") or "").lower() for r in reviews]
    explicit = sum(1 for r in reviews if r.get("incentivized"))
    flagged_in_text = 0
    for t in texts_lc:
        if any(p in t for p in INCENTIVE_PHRASES):
            flagged_in_text += 1
    total_flag = explicit + flagged_in_text
    if not reviews:
        return {"name": "incentivized_disclosure", "weight": 0.10, "score": 50,
                "note": "no reviews — neutral", "details": None}
    ratio = total_flag / len(reviews)
    if ratio >= 0.30:
        score, note = 10, f"{ratio:.0%} of reviews disclose incentive (Vine / free product)"
    elif ratio >= 0.15:
        score, note = 40, f"{ratio:.0%} of reviews disclose incentive"
    elif ratio > 0:
        score, note = 75, f"{ratio:.0%} of reviews disclose incentive — normal Vine presence"
    else:
        score, note = 100, "no incentive disclosures detected"
    return {
        "name": "incentivized_disclosure",
        "weight": 0.10,
        "score": score,
        "note": note,
        "details": {"flagged_ratio": round(ratio, 3), "phrase_hits": flagged_in_text,
                    "explicit_flagged": explicit},
    }


def verified_purchase(reviews: list[dict]) -> dict:
    has_field = [r for r in reviews if "verified" in r]
    if not has_field:
        return {"name": "verified_purchase", "weight": 0.10, "score": 50,
                "note": "no verified-purchase data — neutral", "details": None}
    verified_count = sum(1 for r in has_field if r.get("verified"))
    ratio = verified_count / len(has_field)
    if ratio >= 0.80:
        score, note = 100, f"{ratio:.0%} verified purchases"
    elif ratio >= 0.60:
        score, note = 75, f"{ratio:.0%} verified purchases"
    elif ratio >= 0.40:
        score, note = 45, f"only {ratio:.0%} verified purchases"
    else:
        score, note = 15, f"only {ratio:.0%} verified — most reviews unverified"
    return {
        "name": "verified_purchase",
        "weight": 0.10,
        "score": score,
        "note": note,
        "details": {"ratio": round(ratio, 3),
                    "verified": verified_count, "with_data": len(has_field)},
    }


def burst_pattern(reviews: list[dict]) -> dict:
    """Detect dates unnaturally clustered (review-farming bursts)."""
    dates: list[datetime] = []
    for r in reviews:
        d = r.get("date")
        if not d:
            continue
        try:
            dates.append(datetime.fromisoformat(str(d).split("T", 1)[0]))
        except Exception:  # noqa: BLE001
            continue
    if len(dates) < 5:
        return {"name": "burst_pattern", "weight": 0.10, "score": 50,
                "note": "too few dated reviews — neutral", "details": None}
    dates.sort()
    span_days = (dates[-1] - dates[0]).days or 1
    # Bucket by week and look for any week containing >40% of reviews
    bucket_counts: dict[int, int] = collections.Counter()
    for d in dates:
        week = (d - dates[0]).days // 7
        bucket_counts[week] += 1
    max_week = max(bucket_counts.values())
    burst_ratio = max_week / len(dates)
    if burst_ratio >= 0.50 and span_days >= 60:
        score, note = 10, f"{burst_ratio:.0%} of reviews in a single week over {span_days}d span — burst pattern"
    elif burst_ratio >= 0.30 and span_days >= 60:
        score, note = 40, f"{burst_ratio:.0%} of reviews concentrated in one week"
    else:
        score, note = 100, f"reviews spread evenly across {span_days}d"
    return {
        "name": "burst_pattern",
        "weight": 0.10,
        "score": score,
        "note": note,
        "details": {"span_days": span_days, "max_week_ratio": round(burst_ratio, 3),
                    "total_dated": len(dates)},
    }


# ---- Aggregation ---------------------------------------------------------

def aggregate(signals: list[dict]) -> tuple[int, str]:
    total_w = sum(s["weight"] for s in signals)
    if total_w == 0:
        return 50, "inconclusive"
    weighted = sum(s["score"] * s["weight"] for s in signals) / total_w
    score = int(round(max(0, min(100, weighted))))
    if score >= 70:
        verdict = "trustworthy"
    elif score >= 40:
        verdict = "mixed"
    else:
        verdict = "suspicious"
    return score, verdict


def main() -> int:
    p = argparse.ArgumentParser(description="Analyze a review corpus for fake-review red flags.")
    p.add_argument(
        "--brand",
        default=None,
        help="Optional brand name — included in the output for downstream consumers.",
    )
    args = p.parse_args()

    reviews = load_input()
    if not reviews:
        print(json.dumps({"error": "no review input on stdin"}), file=sys.stderr)
        return 2

    signals = [
        rating_distribution(reviews),
        template_language(reviews),
        vocabulary_diversity(reviews),
        ngram_overlap(reviews),
        incentivized_disclosure(reviews),
        verified_purchase(reviews),
        burst_pattern(reviews),
    ]
    authenticity, verdict = aggregate(signals)

    print(json.dumps({
        "brand": args.brand,
        "review_count": len(reviews),
        "authenticity_score": authenticity,
        "verdict": verdict,
        "signals": signals,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
