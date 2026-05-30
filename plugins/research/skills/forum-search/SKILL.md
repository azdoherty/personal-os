---
name: forum-search
version: 0.1.0
description: Search Hacker News and StackExchange for discussions, answers, and expert commentary on a topic. Use when the user asks for HN or StackOverflow opinions, "what's the consensus on", technical Q&A from forums, or whenever you need engagement-weighted (scored, vote-ranked) discussion data. Returns normalized JSON with vote counts and answer counts.
allowed-tools:
  - Bash
triggers:
  - search hn
  - hacker news on
  - stackoverflow says
  - what's the consensus on
  - forum opinion
---

# forum-search

Search Hacker News (via Algolia) and/or StackExchange sites (Stack Overflow, Super User, Ask Ubuntu, niche communities). Both APIs are free and unauthenticated.

## When to use

- The user explicitly asks for HN or StackExchange results.
- The orchestrator (`/literature-review`) calls this for technical questions, factual queries, or anything where engagement-weighted scoring helps.

Pair with `/reddit-search` and `/web-search` for broad coverage.

## How to invoke

### Hacker News (Algolia)

```bash
${CLAUDE_PLUGIN_ROOT}/skills/forum-search/scripts/hn.sh "<query>" [-n LIMIT] [-t story|comment|all] [-r popularity|recent]
```

- Defaults: `LIMIT=15`, `tags=story`, `rank=popularity`.
- Use `-t comment` for inline expert commentary; `-t all` for both.
- Use `-r recent` when current opinion matters more than all-time popularity.

### StackExchange (Stack Overflow + sibling sites)

```bash
${CLAUDE_PLUGIN_ROOT}/skills/forum-search/scripts/stackexchange.sh "<query>" [-s site1,site2,...] [-n LIMIT]
```

- Default site: `stackoverflow`.
- Multi-site example: `-s stackoverflow,superuser,askubuntu`.
- Other useful sites: `serverfault`, `cooking`, `diy`, `photo`, `woodworking`, `parenting`, `money`, `gardening`, `homebrew`, `coffee`, `gaming`.
- Pick sites that match the question domain. Cooking question → `cooking,seasonedadvice` (no, just `cooking`); product question → `stackoverflow` only if it's technical, otherwise skip SE entirely.

### Calling both

Run them in parallel from Bash (`&` + `wait`) or invoke this skill twice with different scripts. The orchestrator typically calls both and merges results.

## Output schema

JSON array of normalized items:

```json
{
  "source": "hn" | "stackexchange:stackoverflow",
  "title": "...",
  "url": "https://news.ycombinator.com/item?id=..." | "https://stackoverflow.com/questions/...",
  "external_url": "https://..." | null,
  "author": "...",
  "created_utc": 1700000000,
  "score": 258,
  "num_comments": 198,
  "snippet": "first ~400 chars (HTML stripped)",
  "subreddit": null
}
```

## Failure modes

- **HN Algolia returns empty hits:** the query was too narrow — retry without quotes, or fall back to `-r recent`.
- **StackExchange `throttle_violation`:** unauthenticated quota is 300 req/day per IP. If hit, queue the request or skip SE for this session.
- **Wrong site:** if `stackexchange.sh` returns 0 hits, the site name is probably wrong. List of valid sites: https://api.stackexchange.com/docs/sites
