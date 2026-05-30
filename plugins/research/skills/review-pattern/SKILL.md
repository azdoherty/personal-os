---
name: review-pattern
version: 0.1.0
description: Analyze a corpus of product reviews for fake-review red flags — rating distribution skew, generic-marketing template language, vocabulary repetition, near-duplicate pairs, incentivized-review disclosures, verified-purchase ratio, and burst posting patterns. Use when the user pastes or supplies reviews and asks whether they look authentic, or when /literature-review needs a listing-level authenticity check to complement brand-check. Returns an authenticity score 0-100 with per-signal breakdown.
allowed-tools:
  - Bash
triggers:
  - are these reviews fake
  - analyze reviews
  - review authenticity
  - check reviews
  - fake review patterns
---

# review-pattern

Listing-level review-authenticity check. Complements `/brand-check` (which works at the *brand* level) by analyzing the actual review text of a single product listing.

## When to use

- The user pastes Amazon (or other marketplace) reviews and asks if they look real.
- `/literature-review` has a `suspicious` brand from `/brand-check` and you want a second-layer signal on the specific listing.
- The user wants to evaluate a single product where brand-level signals are inconclusive.

Don't use this for cross-brand comparison — that's what `/brand-check` is for.

## Input format

Pipe one of these to the script via stdin:

**JSON array** (preferred — richest signal):

```json
[
  {"text": "...", "rating": 5, "date": "2024-03-14", "verified": true, "reviewer": "u123", "incentivized": false},
  ...
]
```

All fields are optional except `text`. Missing fields → corresponding signals fall back to "neutral".

**Plain text** (when only review bodies are available):

```
First review body.

Second review body.

Third review body.
```

Blank lines separate reviews. Only the text-based signals fire — rating/verified/date signals stay neutral.

## How to invoke

```bash
cat reviews.json | python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-pattern/scripts/analyze_reviews.py [--brand NAME]
```

`--brand` is metadata-only — included in the output for downstream consumers (e.g. `/literature-review` summary).

## Output

```json
{
  "brand": "Allolo",
  "review_count": 50,
  "authenticity_score": 23,
  "verdict": "suspicious",
  "signals": [
    {"name": "rating_distribution", "score": 10, "weight": 0.15,
     "note": "97% 5-star concentration (extreme)", "details": {...}},
    {"name": "template_language", "score": 35, "weight": 0.20,
     "note": "65% of reviews use generic marketing templates",
     "details": {"top_templates": [["highly recommend", 32], ["works great", 28], ...]}},
    {"name": "vocabulary_diversity", "score": 15, "weight": 0.15,
     "note": "very low vocabulary (TTR=0.18) — likely templated"},
    {"name": "ngram_overlap", "score": 0, "weight": 0.20,
     "note": "23% of review pairs near-duplicate — likely copy-paste"},
    {"name": "incentivized_disclosure", "score": 40, "weight": 0.10,
     "note": "18% of reviews disclose incentive"},
    {"name": "verified_purchase", "score": 45, "weight": 0.10,
     "note": "only 50% verified purchases"},
    {"name": "burst_pattern", "score": 10, "weight": 0.10,
     "note": "61% of reviews in a single week over 180d span — burst pattern"}
  ]
}
```

Verdict thresholds: `≥70 trustworthy`, `40–69 mixed`, `<40 suspicious`.

## Signal reference

| Signal | Weight | What it detects |
|---|---|---|
| `rating_distribution` | 15% | ≥95% 5-star = extreme; healthy products are ~70–85% 5-star with some 1-star presence |
| `template_language` | 20% | Generic marketing phrases ("highly recommend", "works great", "exactly what I needed") used by ≥60% of reviews |
| `vocabulary_diversity` | 15% | Type-token ratio across all review text. TTR < 0.25 = heavy repetition |
| `ngram_overlap` | 20% | 4-gram Jaccard similarity ≥ 0.30 between review pairs = likely copy-paste |
| `incentivized_disclosure` | 10% | "received this product in exchange for", "Vine program", "free product" phrases — Amazon Vine is legitimate but a high ratio reduces signal-to-noise |
| `verified_purchase` | 10% | Fraction of reviews marked as verified-purchase. < 60% is a yellow flag |
| `burst_pattern` | 10% | Date clustering — > 50% of reviews in a single week over a 60+ day span is a posting-farm tell |

## Failure modes

- **Plain-text input:** only `template_language`, `vocabulary_diversity`, `ngram_overlap`, and `incentivized_disclosure` fire. The others go neutral, so the score is less reliable. Push the user to grab JSON with metadata if they can.
- **Tiny corpus (< 5 reviews):** `ngram_overlap` and `burst_pattern` fall back to neutral. With < 50 words total, `vocabulary_diversity` also abstains. The verdict on tiny inputs is mostly the rating + template signals.
- **Foreign-language reviews:** the template phrase list is English-only. For mostly-Spanish/Chinese/etc. corpora, run them through translation upstream first, or rely on the language-agnostic signals (ratings, dates, n-gram overlap).

## Limitations vs. ML-based fake-review detection

Academic methods (graph neural networks over user-product-review graphs) catch coordinated reviewer rings that this skill can't see — we have no reviewer history, only the text and metadata of one listing. Treat this as a fast heuristic layer, not the last word. Pair with `/brand-check` for the brand-level view and the user's own judgment for final calls.

## Composition

In `/literature-review`, this skill is invoked when a brand returns `suspicious` from `/brand-check` *and* the user has actually pasted review data. Otherwise, brand-check is enough.
