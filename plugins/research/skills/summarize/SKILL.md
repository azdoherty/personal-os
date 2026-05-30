---
name: summarize
version: 0.1.0
description: Produce a short, cited markdown summary from a ranked list of trust-scored sources. Use after source-trust has ranked the results from reddit-search, forum-search, and web-search. Usually called internally by /literature-review.
allowed-tools:
  - Read
triggers:
  - summarize these sources
  - write up findings
  - compile summary
---

# summarize

Turn a trust-scored array of sources into a tight, useful markdown answer.

## When to use

Called by `/literature-review` after `/source-trust` has produced a ranked array. Can also be invoked manually if you've already gathered + scored sources elsewhere.

## Input

A JSON array of source items, each with `trust` and `trust_reasons`, sorted descending by `trust`. Same shape as `source-trust`'s output.

## Output format

Markdown with these sections. Be brief — total length should fit in one screen unless the user asked for depth.

```markdown
## TL;DR
2-4 sentence direct answer to the question.

## What the trusted sources say
- Bullet 1 with key claim. [^1]
- Bullet 2 with key claim. [^2][^3]
- Bullet 3 (if needed).

## Disagreements / caveats
Any conflicts between high-trust sources, missing info, or things the user
should be skeptical of. Skip the section if there are none worth flagging.

## Verdict
For purchase questions: a recommended pick + a runner-up + the deciding factor.
For factual questions: the consensus answer + confidence level.
For opinion questions: a balanced summary of camps.

## Sources
[^1]: [Title](url) — trust 86, domain prior 92, etc. (1-line provenance)
[^2]: ...
```

## Rules

- **Cite everything.** Every claim in "What the trusted sources say" must have a `[^N]` footnote. Prefer claims supported by ≥2 sources.
- **Trust threshold.** Use only items with `trust ≥ 50` for claims by default. Lower-trust items can appear in "Disagreements" or be ignored.
- **Cap citations at 8.** If there are more high-trust sources, pick the top 8 unique domains.
- **Be honest about gaps.** If the top result has `trust < 60` or there are < 3 sources total, say "limited evidence" in the TL;DR.
- **Don't fabricate.** If the sources don't actually contain the info needed to answer, say so in TL;DR and recommend a follow-up search.
- **No raw JSON in output.** This is the user-facing surface.

## Style

- Active voice. Short sentences.
- Currency, prices, model numbers, dates — preserve exactly as the sources state them.
- For purchase questions, name specific products, not categories.
- Quote sparingly. Paraphrase. Inline quotes only when the exact wording matters.

## Failure modes

- **Empty input:** output `_No sources to summarize._` and stop.
- **All items low-trust:** still produce a TL;DR but lead with a caveat about source quality.
