---
name: literature-review
version: 0.5.0
description: End-to-end literature review for purchase decisions, factual questions, scientific/medical questions, and opinion queries. Use whenever the user asks a question like "should I buy X", "what's the consensus on Y", "what does the research say about Z", "should I invest in W", or anything that would normally require reading multiple forums, Reddit threads, peer-reviewed papers, and review articles. Fans out across Reddit (with engagement metadata), Hacker News, StackExchange, the open web, AND peer-reviewed literature (PubMed, Semantic Scholar, OpenAlex, arXiv); verifies brand legitimacy for purchase questions; scores source trust with evidence-pyramid bonuses for academic sources; returns a short cited summary.
allowed-tools:
  - Bash
  - Read
  - WebSearch
  - WebFetch
  - Task
triggers:
  - literature review
  - research this
  - should i buy
  - what's the consensus
  - what does the internet say
  - help me decide between
---

# literature-review

Orchestrator skill. Takes a question, fans out across source skills, ranks results, and produces a cited summary.

## When to use

- User asks for a research-style answer that would require reading many threads/articles.
- Purchase decisions ("should I buy X vs Y").
- Factual questions where you want sourced corroboration.
- Opinion / consensus questions ("what does Reddit/HN think about...").

Do **not** use this for:
- Simple lookups answered by one Wikipedia paragraph (just answer directly).
- Code questions answered by a single Stack Overflow result (use `/forum-search` solo).
- Real-time data (stock prices, sports scores) — wrong tool.

## Workflow

### Step 1: Classify intent

Pick one — `purchase`, `factual`, `scientific`, `medical`, `opinion`, `technical`, or `investment`. Use this to choose sources and filters:

| Intent | Reddit | Forum (HN+SE) | Web | Academic | Notes |
|---|---|---|---|---|---|
| `purchase` | ✓ niche subs | HN only | ✓ wirecutter/rtings/consumerreports/anandtech | ✓ if claims are clinical/mechanistic | always run `/brand-check` |
| `scientific` | optional | ✓ | ✓ gov/edu/nature | **✓ primary** (pubmed,openalex,semantic_scholar — and arxiv for physics/CS) | trust academic >> web >> forum |
| `medical` | ✓ patient experience subs | optional | ✓ NIH/CDC/Mayo | **✓ primary** (pubmed first) | flag personal anecdotes vs evidence |
| `factual` | optional | ✓ | ✓ primary sources | ✓ if claim hinges on research | web first, academic for verification |
| `technical` | optional | ✓ (SO + niche SE) | ✓ docs/github | ✓ if research-y (ML, distributed systems) | |
| `opinion` | ✓ | ✓ | ✓ | optional | community-experience-heavy |
| `investment` | ✓ subs (e.g. realestateinvesting, stocks, personalfinance) | optional | ✓ industry pubs | ✓ openalex,semantic_scholar (q-fin on arxiv) | corroboration > anecdote |

Mixed-intent is common — "is this red-light therapy device worth it?" is `purchase` + `medical` (need brand-check AND the academic evidence for the mechanism). Run all relevant source skills and let `/source-trust` rank them.

### Step 2: Fan out in parallel

Run source skills concurrently. Two options — both correct:

**Option A — direct Bash (preferred for speed):**

```bash
# Run all source scripts in the background, capture into temp files, wait, then merge.
TMP=$(mktemp -d)
${CLAUDE_PLUGIN_ROOT}/skills/reddit-search/scripts/search.sh  "$QUERY" -n 10 > "$TMP/reddit.json" &
${CLAUDE_PLUGIN_ROOT}/skills/forum-search/scripts/hn.sh        "$QUERY" -n 10 > "$TMP/hn.json" &
${CLAUDE_PLUGIN_ROOT}/skills/forum-search/scripts/stackexchange.sh "$QUERY" -n 10 > "$TMP/se.json" &
# Academic — add when intent is scientific/medical/factual/investment/research-y purchase
python3 ${CLAUDE_PLUGIN_ROOT}/skills/academic-search/scripts/search.py "$QUERY" \
        --sources pubmed,openalex,semantic_scholar -n 8 --no-abstracts > "$TMP/academic.json" &
wait
# WebSearch is a Claude tool, not a shell command — call it from the surrounding
# Claude turn and write its normalized JSON to "$TMP/web.json".
jq -s 'add' "$TMP"/*.json > "$TMP/all.json"
```

Pick `--sources` for academic based on the domain (see academic-search SKILL.md cheat sheet):
- Medical → `pubmed,openalex,semantic_scholar`
- Real estate / finance → `openalex,semantic_scholar,arxiv`
- ML / CS / engineering → `arxiv,semantic_scholar,openalex`
- Cross-disciplinary → all four (default)

**Option B — Task subagents (preferred for isolation):**

Spawn one Task subagent per source (`subagent_type: "general-purpose"` or `"Explore"`). Each subagent invokes its source skill and returns normalized JSON in a single message. The orchestrator merges the JSON arrays. Slower than Option A but better when individual sources need their own reasoning loop (e.g. choosing the right StackExchange site).

For most questions Option A is fine. Use Option B when WebSearch needs multi-step reasoning (e.g., "search, read top 3 articles, summarize each").

### Step 3 (purchase intent only): Brand-check each candidate

If the intent is `purchase`, before scoring you should verify every distinct brand named in the merged results. This catches shell brands, Amazon-only listings, and review-farmed products *before* they end up in the summary.

```bash
# 1. Extract distinct brand candidates. For purchase questions, you typically
#    already know the candidates (the user named them, or your initial pass
#    surfaced 3-5 products). Make a list:
BRANDS=("Auravex" "Halcyra" "Vosmith")

# 2. For each brand, gather independent reviewer hits via WebSearch (see
#    brand-check SKILL.md for the category-specific allowed_domains lists),
#    then run brand-check:
echo "{}" > "$TMP/brand_legitimacy.json"
for B in "${BRANDS[@]}"; do
  # (You — Claude — call WebSearch here and count substantive review hits → REVIEWER_HITS)
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/brand-check/scripts/brand_check.py \
      "$B" --reviewer-hits "$REVIEWER_HITS" --quick > "$TMP/bc_$B.json"
  # Append { "<resolved-domain-or-amazon-listing-path>": <legitimacy> } to brand_legitimacy.json
done
```

The `brand_legitimacy.json` map should use bare domains (`auravex.io`, `halcyra.com`) for brand-owned sites and `domain/path-prefix` strings (`amazon.com/dp/B0XYZ` lower-cased) for marketplace listings.

### Step 3.5 (medical/scientific intent): Grade claims with medical-evidence

If intent is `medical` (or a scientific health question), invoke the `medical-evidence` skill
before scoring. It enumerates the full solution space, decomposes results into atomic claims,
and grades each with `grade_claim.py`. Its ranked ledger — not the raw source list — becomes
the backbone of the summary. Do not hand-wave a recommendation past it; a `mechanism-only` or
`marketing-claim` verdict must be reported as such.

### Step 4: Score

```bash
cat "$TMP/all.json" \
  | python3 ${CLAUDE_PLUGIN_ROOT}/skills/source-trust/scripts/score.py \
      --brand-legitimacy "$TMP/brand_legitimacy.json" \
  > "$TMP/scored.json"
```

Omit `--brand-legitimacy` for factual/opinion/technical questions where the marketplace-listing concern doesn't apply. Output is sorted descending by trust.

### Step 5: Summarize

Read `$TMP/scored.json` and apply the `/summarize` skill's instructions (`${CLAUDE_PLUGIN_ROOT}/skills/summarize/SKILL.md`). Produce the markdown summary in the conversation.

For purchase questions specifically: include a **Brand legitimacy** subsection under "Disagreements / caveats" listing any brand whose `brand-check` came back `inconclusive` or `suspicious`. Recommend skipping products from suspicious brands explicitly.

For scientific / medical / investment questions: lead the summary with the strongest academic evidence (highest-trust items with `study_type` in `Meta-Analysis | Systematic Review | RCT`). When community anecdotes (Reddit) contradict the peer-reviewed evidence, weight the evidence and label the anecdotes as such. When evidence is thin (no meta-analyses, only individual studies or preprints), say so in the TL;DR.

### Step 6: Offer follow-up

After the summary, offer:
- "Want me to dig deeper into [specific source]?"
- "Should I save this as a learning?" (if gstack `/learn` is available)

## Query refinement tips

- **Purchase, plural options:** for "X vs Y", run two queries — one with `X Y comparison`, one with each name solo — and merge.
- **Year-relevant questions:** if the answer is likely to have changed, append the current year (e.g. "best mechanical keyboard 2026").
- **Niche subs:** for purchases, pre-pick subs (`-s buyitforlife,bifl`) — broad reddit search dilutes signal.

## Failure modes

- **All sources empty:** the query was too narrow. Drop the most specific term, retry once. If still empty, tell the user and suggest rephrasings.
- **One source 403/timeout:** Reddit can be flaky. Note the partial coverage in the final summary's "Disagreements/caveats" section.
- **Rate limit:** if HN/SE return throttle errors, fall back to web-only and flag it.
- **Token blow-up:** if scored sources are > 50 items, the script already returns sorted; trim to top 15 before passing to summarize.

## Example invocation

User: "Should I buy a Steelcase Gesture or a Herman Miller Embody?"

1. Intent: `purchase`. Subs: `buyitforlife,ergonomics,officechairs`. Web domains hint: rtings, wirecutter, consumerreports.
2. Run reddit + HN + web in parallel (skip SE — not a coding question).
3. Score.
4. Summarize as: TL;DR (1 pick + 1 runner-up + key tradeoff), claims, disagreements, verdict, sources.
