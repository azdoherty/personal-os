#!/usr/bin/env python3
"""source-trust/score.py: score sources 0-100.

Input:  JSON array of normalized source items on stdin (the same shape as
        emitted by reddit-search, forum-search, web-search).
Output: JSON array on stdout with two extra fields per item: `trust` (0-100
        integer) and `trust_reasons` (list of strings).

Components:
  - domain prior      from references/domain-trust.json (default 40)
  - recency           100% if ≤ 6 months, linear decay to 50% by 3 years, 50% floor
  - brand legitimacy  optional, from --brand-legitimacy <json>; multiplier 0-1
  - engagement        log-scaled bonus from score/num_comments (max +15)
  - corroboration     +10 if ≥ 2 other sources agree on a key term/claim

Recency and brand legitimacy are *multiplicative* factors applied around the
default-prior center of 40. Engagement and corroboration are additive bonuses.
The final score is clipped to [0, 100].

Usage:
  source-trust/score.py [--trust-map PATH] [--brand-legitimacy PATH]

  --brand-legitimacy JSON example:
    {
      "auravex.io": 84,
      "halcyra.com": 71,
      "amazon.com/dp/B0XYZ12345": 25
    }
  Keys are bare domains or "domain/path-prefix"; values are 0-100 scores.
  Matching items get prior * (score/100) before recency. Strong way to
  downweight suspicious-brand Amazon listings.

Tunable knobs are at the top of the file.
"""

import argparse
import collections
import json
import math
import os
import re
import sys
import time
import urllib.parse


DEFAULT_DOMAIN_PRIOR = 40
MIN_RECENCY_FACTOR = 0.5
RECENCY_FULL_S = 180 * 86400  # 6 months at full strength
RECENCY_FLOOR_S = 3 * 365 * 86400  # decay to 50% by 3 years
MAX_ENGAGEMENT_BONUS = 15
CORROBORATION_BONUS = 10
CORROBORATION_MIN_MATCHES = 2


def domain_of(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except Exception:  # noqa: BLE001
        return ""
    host = host.lower().lstrip(".")
    return host[4:] if host.startswith("www.") else host


def load_trust_map(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        k.lower(): v
        for k, v in raw.items()
        if not k.startswith("_") and isinstance(v, (int, float))
    }


def domain_prior(url: str, trust_map: dict) -> tuple[int, str]:
    d = domain_of(url)
    if not d:
        return DEFAULT_DOMAIN_PRIOR, "unknown domain"
    if d in trust_map:
        return int(trust_map[d]), f"domain={d}"
    # try parent domain (e.g. en.wikipedia.org -> wikipedia.org)
    parts = d.split(".")
    for i in range(1, len(parts) - 1):
        parent = ".".join(parts[i:])
        if parent in trust_map:
            return int(trust_map[parent]), f"parent_domain={parent}"
    return DEFAULT_DOMAIN_PRIOR, f"domain={d} (default)"


def recency_factor(created_utc) -> tuple[float, str]:
    if not created_utc:
        return 1.0, "no date (neutral)"
    age_s = max(0, int(time.time()) - int(created_utc))
    if age_s <= RECENCY_FULL_S:
        return 1.0, f"{age_s // 86400}d old"
    if age_s >= RECENCY_FLOOR_S:
        return MIN_RECENCY_FACTOR, f"{age_s // 86400}d old (floor)"
    frac = (age_s - RECENCY_FULL_S) / (RECENCY_FLOOR_S - RECENCY_FULL_S)
    factor = 1.0 - frac * (1.0 - MIN_RECENCY_FACTOR)
    return factor, f"{age_s // 86400}d old"


def engagement_bonus(score, num_comments) -> tuple[int, str]:
    if score is None and num_comments is None:
        return 0, "no engagement signal"
    s = score or 0
    c = num_comments or 0
    if s <= 0 and c <= 0:
        return 0, "no engagement"
    raw = math.log10(1 + max(s, 0)) * 4 + math.log10(1 + max(c, 0)) * 3
    bonus = min(MAX_ENGAGEMENT_BONUS, int(round(raw)))
    return bonus, f"score={s}, comments={c}"


# Evidence-pyramid bonus for academic items. Only fires when an item carries
# a study_type field (academic-search outputs). Reddit/forum/web items skip
# this entirely (no field) and get +0.
_STUDY_TYPE_BONUS = {
    "meta-analysis": 8,
    "metaanalysis": 8,
    "systematic review": 7,
    "systematicreview": 7,
    "practice guideline": 6,
    "practiceguideline": 6,
    "randomized controlled trial": 5,
    "rct": 5,
    "clinical trial": 4,
    "clinicaltrial": 4,
    "cohort study": 3,
    "review": 3,
    "comparative study": 2,
    "journalarticle": 1,
    "article": 1,
    "case report": -2,
    "casereport": -2,
    "preprint": -3,
    "editorial": -3,
    "letter": -4,
    "news": -4,
    "opinion": -4,
}


def study_type_bonus(study_type) -> tuple[int, str]:
    if not study_type:
        return 0, ""
    key = str(study_type).lower().strip()
    # try exact, then collapsed (no spaces/hyphens)
    if key in _STUDY_TYPE_BONUS:
        return _STUDY_TYPE_BONUS[key], f"study_type={study_type}"
    collapsed = re.sub(r"[\s-]+", "", key)
    if collapsed in _STUDY_TYPE_BONUS:
        return _STUDY_TYPE_BONUS[collapsed], f"study_type={study_type}"
    return 0, f"study_type={study_type} (no bonus mapping)"


_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "is", "are", "was", "were", "be", "been", "as", "at", "by",
    "this", "that", "it", "from", "what", "how", "why", "best", "good",
    "vs", "vs.", "i", "we", "you", "they",
}


def keywords(item: dict) -> set[str]:
    text = " ".join(
        str(item.get(k) or "") for k in ("title", "snippet", "external_url")
    ).lower()
    tokens = re.findall(r"[a-z][a-z0-9\-]{3,}", text)
    return {t for t in tokens if t not in _STOPWORDS}


def corroboration_map(items: list[dict]) -> dict[str, int]:
    """How many distinct sources mention each keyword."""
    src_keywords: list[tuple[str, set[str]]] = []
    for it in items:
        src_keywords.append((domain_of(it.get("url") or ""), keywords(it)))
    counter: dict[str, int] = collections.Counter()
    for domain, kws in src_keywords:
        seen_for_this = set()
        for kw in kws:
            if kw in seen_for_this:
                continue
            seen_for_this.add(kw)
            counter[kw] += 1
    return counter


def corroboration_bonus(item: dict, corr: dict[str, int]) -> tuple[int, str]:
    kws = keywords(item)
    matched = [k for k in kws if corr.get(k, 0) >= CORROBORATION_MIN_MATCHES]
    if len(matched) < 3:
        return 0, "no corroboration"
    # cap, give at most CORROBORATION_BONUS
    return CORROBORATION_BONUS, f"corroborated terms: {sorted(matched)[:5]}"


def brand_legitimacy_factor(url: str, brand_map: dict) -> tuple[float, str]:
    """Look up brand legitimacy by URL match.

    `brand_map` keys are either bare domains ("auravex.io") or
    domain+path-prefix ("amazon.com/vosmith"). Values are 0-100 legitimacy
    scores. The returned factor multiplies the domain prior.
    """
    if not brand_map:
        return 1.0, "no brand-legitimacy map"
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:  # noqa: BLE001
        return 1.0, "url parse failed"
    host = (parsed.hostname or "").lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    path = (parsed.path or "").lower()
    matched_key = None
    matched_score = None
    for key, val in brand_map.items():
        if not isinstance(val, (int, float)):
            continue
        key_lc = key.lower()
        if "/" in key_lc:
            kd, _, kp = key_lc.partition("/")
            if host == kd or host.endswith("." + kd):
                if path.startswith("/" + kp):
                    matched_key, matched_score = key_lc, val
                    break
        else:
            if host == key_lc or host.endswith("." + key_lc):
                matched_key, matched_score = key_lc, val
                break
    if matched_score is None:
        return 1.0, "no brand match"
    # Piecewise so "legitimate" brands aren't penalized:
    #   legitimacy >= 70  -> factor 1.0    (no haircut)
    #   legitimacy 40..69 -> factor 0.5..1.0 linear
    #   legitimacy <  40  -> factor 0.0..0.5 linear (suspicious collapses)
    if matched_score >= 70:
        factor = 1.0
    elif matched_score >= 40:
        factor = 0.5 + 0.5 * (matched_score - 40) / 30.0
    else:
        factor = max(0.0, matched_score / 80.0)
    return factor, f"brand={matched_key} legitimacy={int(matched_score)}"


def score_item(item: dict, trust_map: dict, corr: dict[str, int], brand_map: dict) -> dict:
    prior, prior_reason = domain_prior(item.get("url") or "", trust_map)
    recency, recency_reason = recency_factor(item.get("created_utc"))
    engagement, engagement_reason = engagement_bonus(
        item.get("score"), item.get("num_comments")
    )
    corrob, corrob_reason = corroboration_bonus(item, corr)
    brand_factor, brand_reason = brand_legitimacy_factor(item.get("url") or "", brand_map)
    study, study_reason = study_type_bonus(item.get("study_type"))

    # apply recency multiplicatively around the "neutral" center of 40
    centered = (prior - DEFAULT_DOMAIN_PRIOR) * recency + DEFAULT_DOMAIN_PRIOR
    # apply brand legitimacy as a straight multiplier on the prior (no centering).
    # A suspicious brand (factor → 0) should collapse trust to near 0, even when
    # the host domain's prior is the default. Only applied when a brand match
    # exists; otherwise brand_factor is 1.0 and this is a no-op.
    centered = centered * brand_factor
    final = centered + engagement + corrob + study
    final = int(max(0, min(100, round(final))))

    out = dict(item)
    out["trust"] = final
    reasons = [
        f"prior {prior} ({prior_reason})",
        f"recency x{recency:.2f} ({recency_reason})",
        f"brand x{brand_factor:.2f} ({brand_reason})",
        f"engagement +{engagement} ({engagement_reason})",
        f"corroboration +{corrob} ({corrob_reason})",
    ]
    if study_reason:
        sign = "+" if study >= 0 else ""
        reasons.append(f"evidence {sign}{study} ({study_reason})")
    out["trust_reasons"] = reasons
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Score sources 0-100.")
    default_trust = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "references", "domain-trust.json",
    )
    p.add_argument("--trust-map", default=default_trust, help="Path to domain-trust.json")
    p.add_argument(
        "--brand-legitimacy",
        default=None,
        help="Path to JSON map of {domain-or-domain-prefix: 0-100 legitimacy score}.",
    )
    args = p.parse_args()

    raw = sys.stdin.read().strip()
    if not raw:
        print("[]")
        return 0
    items = json.loads(raw)
    if not isinstance(items, list):
        print(json.dumps({"error": "input must be a JSON array of source items"}), file=sys.stderr)
        return 2

    trust_map = load_trust_map(args.trust_map)
    brand_map: dict = {}
    if args.brand_legitimacy and os.path.isfile(args.brand_legitimacy):
        with open(args.brand_legitimacy, encoding="utf-8") as f:
            brand_map = json.load(f) or {}
    corr = corroboration_map(items)
    scored = [score_item(it, trust_map, corr, brand_map) for it in items]
    scored.sort(key=lambda x: -x["trust"])
    print(json.dumps(scored, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
