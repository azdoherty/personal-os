---
name: brand-check
version: 0.2.0
description: Score a brand's legitimacy 0-100 to detect shell-brand / review-farmed / Amazon-only listings AND surface documented integrity issues (recalls, lawsuits, false advertising) before recommending their products. Use whenever you're about to recommend a product from a brand you don't recognize, when sources are dominated by Amazon listings or vendor blogs, or when the user explicitly asks "is this brand legit / real / trustworthy?". Returns a structured verdict (legitimate / inconclusive / suspicious) with supporting signals.
allowed-tools:
  - Bash
  - WebSearch
triggers:
  - is this brand legit
  - is brand real
  - verify brand
  - check brand reputation
  - is it a scam
  - fake reviews
---

# brand-check

Quantitative legitimacy check for a brand. Combines four signals into a 0–100 score:

| Signal | Weight | How it's gathered |
|---|---|---|
| Organic Reddit discussion | 35% | Subprocess call to `/reddit-search` (PullPush only — no RSS fallback so we count only items with real engagement data). Optional `--keywords` flag filters brand-name collisions. |
| Independent reviewer coverage | 30% | `WebSearch` with `allowed_domains` restricted to a curated list of independent reviewers |
| Brand website footprint | 15% | Direct HTTP fetch of common URL patterns; detects parked domains, Shopify/Squarespace/Wix platforms, about/contact/privacy/shop markers |
| Brand integrity history | 20% | `WebSearch` for documented controversies — recalls, lawsuits, false advertising, fabricated endorsements. Hits drag the brand's score down hard. |

Verdict thresholds: `≥70 legitimate`, `40–69 inconclusive`, `<40 suspicious`.

## When to use

- Before recommending any product whose brand you don't independently recognize.
- When `/literature-review` is summarizing a purchase question and ≥1 candidate brand has only Amazon/vendor sources.
- When the user explicitly asks ("is this brand legit", "are the reviews fake").

Skip when the brand is universally well-known (Apple, Sony, Toyota — domain priors already handle these in `/source-trust`).

## How to invoke

**Step 1** — gather independent reviewer hits via `WebSearch`. Use these domain allow-lists by category:

| Category | `allowed_domains` |
|---|---|
| Electronics / tech | `["rtings.com", "anandtech.com", "wareable.com", "theverge.com", "arstechnica.com", "tomshardware.com", "pcmag.com"]` |
| Health / wellness gear | `["consumerreports.org", "wareable.com", "gadgetsandwearables.com", "garagegymreviews.com", "rtings.com"]` |
| Outdoor / sports | `["outdoorgearlab.com", "garagegymreviews.com", "rei.com/blog"]` |
| Home / furniture | `["consumerreports.org", "thespruce.com"]` |
| Watches | `["hodinkee.com", "watchuseek.com"]` |

Note: `wirecutter.com` is blocked for Anthropic's user agent; omit it from `allowed_domains` and search separately if you need it.

Search query: `"<brand>" review`. Count how many of the returned results are *substantive coverage* (an actual review article, not just a passing mention) — call this `N`.

**Step 2** — gather integrity-history hits via `WebSearch` (no domain restriction). Query:
`"<brand>" controversy OR lawsuit OR recall OR fake OR misleading OR fabricated OR settlement`.
Count how many results are *substantive incidents* documented by credible sources (CPSC, FTC, news media, court filings, BBB) — call this `M`. Skip stories about *other companies with similar names* (e.g. for "Lifepro", the wellness brand's CPSC recall counts; "LifePro Financial Services" IUL fraud doesn't because it's a different legal entity).

**Step 3** — run the script:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/brand-check/scripts/brand_check.py "<brand>" \
    --reviewer-hits <N> \
    --integrity-hits <M> \
    --keywords "<topic1>,<topic2>,..." \
    [--known-domain <brand.com>] \
    [--quick]
```

Flags:
- `--reviewer-hits N`: count from Step 1. Omit only if WebSearch is unavailable (neutral fallback).
- `--integrity-hits M`: count from Step 2. **Always pass 0 if you actively searched and found nothing** — omitting this defaults to neutral (50), which under-credits clean brands.
- `--keywords "..."`: comma-separated category keywords. Required for any brand with a generic-English name (`Lifepro`, `Apple`, `Bear`, `Element`) — otherwise the Reddit signal will be polluted by name collisions. Example for a wellness brand: `--keywords "therapy,vibration,massage,fitness,recovery,wellness"`.
- `--known-domain`: skip URL guessing if you already know the brand's homepage.
- `--quick`: skip the second Reddit query. ~2x faster.

## Output

```json
{
  "brand": "Auravex",
  "legitimacy": 84,
  "verdict": "legitimate",
  "signals": [
    {"name": "reddit_organic", "value": 11, "weight": 0.40, "score": 95,
     "note": "11 relevant posts, total engagement 247",
     "details": {"relevant_posts": 11, "total_engagement": 247, "examples": [...]}},
    {"name": "independent_reviewer", "value": 3, "weight": 0.35, "score": 100,
     "note": "3 independent reviewer hits"},
    {"name": "website_footprint", "value": "https://auravex.io", "weight": 0.25, "score": 65,
     "note": "partial footprint (2/4 markers)"}
  ],
  "checked_at": 1764500000
}
```

## How to use the verdict

| Verdict | Action |
|---|---|
| `legitimate` (≥70) | Treat the brand's product pages and vendor blogs as normal sources. Apply usual domain priors. |
| `inconclusive` (40–69) | Cite the brand's claims but flag that independent corroboration is limited. Lower confidence in any product-specific recommendation. |
| `suspicious` (<40) | **Do not recommend the product.** If asked to compare, include the brand only with a clear "no independent footprint" warning. Suggest the user pick a brand with verified organic discussion. |

## Wiring into source-trust

`/source-trust` can ingest brand-check output via `--brand-legitimacy <path>`:

```bash
# 1. Run brand-check on each candidate brand, save as a domain → legitimacy map
echo '{"auravex.io": 84, "halcyra.com": 71, "amazon.com/vosmith": 22}' > /tmp/brands.json

# 2. Pass to source-trust
cat all_sources.json | source-trust/scripts/score.py --brand-legitimacy /tmp/brands.json
```

When a source's URL matches a key in the legitimacy map, its domain prior is multiplied by `legitimacy/100` before recency. So a suspicious-brand Amazon listing collapses from prior 30 → 7, dropping out of any summary.

## Failure modes

- **No internet:** the script returns mostly-neutral scores (50) with notes. The aggregation still produces a verdict, but treat it as inconclusive.
- **PullPush timeout:** Reddit signal degrades to neutral. Re-run with `--quick` if speed matters.
- **WebSearch unavailable:** pass `--reviewer-hits 0` only if you've actually checked and found nothing; otherwise omit the flag so it's marked neutral, not failing.
- **Brand name is ambiguous** (e.g. "Apple", "Amazon"): the Reddit/WebSearch signals will be dominated by the more-famous referent. Use `--known-domain` to anchor or skip brand-check entirely.

## Examples

| Brand | Verdict | Why |
|---|---|---|
| Auravex | `legitimate` (88) | Organic r/golf + r/redlighttherapy threads; Wareable + Garage Gym Reviews coverage; Shopify site at auravex.io; no documented controversies |
| Halcyra | `legitimate` (84) | Tennisnerd + Trail and Kale + Gadgets & Wearables reviews; Shopify site at halcyra.com; no documented controversies |
| Lifepro | `suspicious` (33) | Has reviewer coverage (Consumer Reports, Wareable, GGR) BUT 4 documented integrity issues: CPSC sauna-blanket recall + 32 burn injuries, active product-liability lawsuits, false PEMF advertising, fabricated medical-expert endorsement. The integrity signal drags an otherwise covered brand to suspicious. |
| Vosmith | `suspicious` (23) | Zero organic Reddit RLT discussion (after keyword filter); no independent reviewer coverage; vosmith.com is HugeDomains-parked |
