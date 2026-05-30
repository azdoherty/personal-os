# research

A Claude Code plugin for answering questions you don't have time to research yourself — purchase decisions, factual lookups, opinion-of-the-internet style queries.

## How it works

You ask `/literature-review "should I buy X or Y?"` (or just describe the question). The orchestrator:

1. Classifies intent (`purchase` | `factual` | `opinion`).
2. Fans out across Reddit, Hacker News, StackExchange, and the web in parallel.
3. Scores each source for trust (domain prior + recency + engagement + corroboration).
4. Produces a short markdown summary with inline citations.

## Skills

| Skill | Purpose |
|---|---|
| `/literature-review` | Orchestrator — end-to-end research and summary. |
| `/reddit-search` | Search Reddit (public JSON, no auth). |
| `/forum-search` | Search Hacker News + StackExchange. |
| `/web-search` | Wraps Claude's built-in WebSearch with research-friendly output. |
| `/source-trust` | Score a list of sources 0–100. (Usually called internally.) |
| `/summarize` | Produce a cited markdown summary from scored sources. (Usually called internally.) |

## Install

From the marketplace root (`personal-os/`):

```
claude plugin marketplace add .
claude plugin install research@personal-os
```

Then `/reload-plugins` in your Claude Code session.

## Status

v0.1 — public/unauthenticated APIs only. Reddit OAuth, Tavily/Brave search, and persistent research history are out of scope for this version.
