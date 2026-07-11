# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

`personal-os` is a Claude Code **plugin marketplace** (declared in `.claude-plugin/marketplace.json`) that currently hosts one plugin: `research` at `plugins/research/`. Add new plugins by dropping them under `plugins/` and appending an entry to the marketplace manifest.

The `research` plugin (v0.5.0, 9 skills) does literature review for purchases, scientific/medical questions, and other "I need to read 50 threads/papers" research tasks. It fans out across Reddit, HN/StackExchange, the open web, and peer-reviewed literature (PubMed, Semantic Scholar, OpenAlex, arXiv), then trust-scores and summarizes.

The `rental` plugin (v0.1.0, 6 skills) analyzes local 2–4 unit multifamily listings for long-term rental investment: it ingests a Redfin CSV export, screens with a zero-API rent heuristic, pauses for human pruning, enriches the shortlist via RentCast, and reports cash-on-cash returns across price scenarios. Shared logic lives in `plugins/rental/lib/` (stdlib-only, unit-tested); skills are thin CLI wrappers. Config (with the RentCast key) lives in the OS config dir, never the repo.

## Common commands

```bash
# Validate manifests after any change
claude plugin validate .                           # marketplace
claude plugin validate plugins/research            # plugin

# After bumping plugin version
claude plugin update research@personal-os          # restart Claude Code to apply
# In an interactive Claude Code session
/reload-plugins                                    # picks up SKILL.md description changes

# Refresh the CPSC recall corpus used by brand-check (run monthly-ish)
python3 plugins/research/skills/brand-check/scripts/refresh_recall_corpus.py --years 5

# Run a skill's script directly (useful when iterating)
python3 plugins/research/skills/reddit-search/scripts/search.py "ergonomic chair" -s buyitforlife
python3 plugins/research/skills/academic-search/scripts/search.py "vitamin D deficiency treatment" --sources pubmed,openalex
python3 plugins/research/skills/brand-check/scripts/brand_check.py "Auravex" --reviewer-hits 3 --integrity-hits 0 --keywords "therapy,light"
cat sources.json | python3 plugins/research/skills/source-trust/scripts/score.py

# Rental plugin — run the test suite
cd plugins/rental && python -m pytest -v

# Rental pipeline (after /setup): ingest -> screen -> [prune] -> enrich -> report
python plugins/rental/skills/ingest-listings/scripts/ingest.py redfin.csv > props.json
```

There are no automated tests yet — verification happens by running the scripts directly against live APIs.

## Architecture

### Marketplace → plugin → skill

`marketplace.json` lists plugins; each plugin has its own `.claude-plugin/plugin.json` and a `skills/<skill-name>/SKILL.md` per skill. Skills are surfaced to Claude Code by their SKILL.md frontmatter (`name`, `description`, `triggers`) and execute via bundled scripts under `skills/<skill-name>/scripts/`.

### research plugin: skill composition

The plugin is organized in three layers — read SKILL.md files in this order to understand what's going on:

1. **Source skills** (parallel fetchers, all output the same normalized JSON shape):
   - `reddit-search` — Reddit via PullPush archive (with engagement metadata) + RSS fallback
   - `forum-search` — HN Algolia + StackExchange API
   - `web-search` — wraps Claude's built-in `WebSearch` / `WebFetch`
   - `academic-search` — PubMed + Semantic Scholar + OpenAlex + arXiv, deduped by DOI

2. **Trust + verification skills** (operate on the normalized JSON):
   - `brand-check` — 5-signal brand legitimacy: Reddit organic, independent reviewer hits (passed in from WebSearch), website footprint (with Shopify/Squarespace/parked-domain detection), domain age via RDAP, and integrity history (auto-detected from a local CPSC recall corpus + manual WebSearch hits)
   - `review-pattern` — listing-level review authenticity (rating skew, template language, n-gram duplicates, burst posting, etc.)
   - `source-trust` — combines `domain-prior × recency × brand-legitimacy + engagement + corroboration + study-type-bonus` into a 0–100 trust score

3. **Orchestration + output**:
   - `literature-review` — classifies user intent (`purchase | scientific | medical | investment | technical | opinion | factual`), fans out across the right source skills in parallel, runs brand-check for purchases, scores, and hands off to summarize
   - `summarize` — produces the user-facing markdown with citations

The normalized item schema all skills agree on lives in the `reddit-search` SKILL.md output section; `academic-search` puts `citation_count` into the `score` field so the engagement bonus in `source-trust` fires uniformly across web, forum, and academic items.

### source-trust scoring (the central formula)

```
final_trust = clip(0, 100,
    ((domain_prior - 40) × recency_factor + 40) × brand_legitimacy_factor
    + engagement_bonus + corroboration_bonus + study_type_bonus
)
```

- `domain_prior` is looked up in `plugins/research/references/domain-trust.json` (default 40)
- `recency_factor` decays from 1.0 (≤6 mo) to 0.5 (≥3 yr)
- `brand_legitimacy_factor` is 1.0 unless a `--brand-legitimacy` map is supplied; piecewise: ≥70 = no penalty, <40 = collapse
- `engagement_bonus` is log-scaled from `score + num_comments` (max +15)
- `corroboration_bonus` is +10 if ≥3 of an item's content keywords appear in ≥2 other items
- `study_type_bonus` rewards the evidence pyramid (Meta-Analysis +8, RCT +5, Preprint -3, etc.)

### brand-check signal weights (5-signal, sums to 1.0)

| Signal | Weight | Source |
|---|---|---|
| `reddit_organic` | 0.30 | `reddit-search` subprocess (PullPush only) — supports `--keywords` to filter brand-name collisions |
| `independent_reviewer` | 0.25 | WebSearch hits passed in via `--reviewer-hits N` |
| `website_footprint` | 0.15 | Direct HTTP fetch; detects parked domains (HugeDomains/Sedo/etc.) and recognizes Shopify/Squarespace/Wix/Webflow/BigCommerce/WooCommerce platforms |
| `domain_age` | 0.10 | RDAP lookup (rdap.org for most TLDs, direct Verisign/Identity Digital for .com/.io) |
| `brand_integrity` | 0.20 | CPSC corpus auto-lookup + `--integrity-hits N` for WebSearch-found controversies |

Verdict thresholds: ≥70 `legitimate`, 40–69 `inconclusive`, <40 `suspicious`.

## Conventions for adding to this repo

- **A new plugin in this marketplace**: create `plugins/<name>/.claude-plugin/plugin.json` + `skills/...`, then append an entry to `.claude-plugin/marketplace.json`. Validate with `claude plugin validate plugins/<name>` and `claude plugin validate .`.
- **A new source skill in `research`**: emit the same normalized JSON shape (`source`, `title`, `url`, `created_utc`, `score`, `num_comments`, `snippet`, `subreddit`) so `source-trust` and `summarize` handle it without changes. Stuff the equivalent of upvotes/citations into `score`.
- **A new domain to trust**: add it to `plugins/research/references/domain-trust.json`. Default prior is 40; the file has comments documenting the 4 trust tiers.
- **A new skill that depends on a Claude-only tool** (WebSearch, etc.): have the orchestrator call the tool and pass results to the script via a flag (the `brand-check` pattern with `--reviewer-hits` / `--integrity-hits`). Scripts must not assume Claude tools are available.
- **Version bumps**: update `plugins/research/.claude-plugin/plugin.json` and run `claude plugin update research@personal-os`. SKILL.md frontmatter versions are informational; the manifest version is authoritative.

Stdlib-only Python (no pip dependencies); shell scripts depend on `curl` and `jq`.

## gstack

The user has the `gstack` plugin installed globally. Use the `/browse` skill from gstack for all web browsing in this repo. Never use `mcp__claude-in-chrome__*` tools.

Available gstack skills:

- /office-hours
- /plan-ceo-review
- /plan-eng-review
- /plan-design-review
- /design-consultation
- /design-shotgun
- /design-html
- /review
- /ship
- /land-and-deploy
- /canary
- /benchmark
- /browse
- /connect-chrome
- /qa
- /qa-only
- /design-review
- /setup-browser-cookies
- /setup-deploy
- /setup-gbrain
- /retro
- /investigate
- /document-release
- /document-generate
- /codex
- /cso
- /autoplan
- /plan-devex-review
- /devex-review
- /careful
- /freeze
- /guard
- /unfreeze
- /gstack-upgrade
- /learn
