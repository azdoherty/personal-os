---
name: reddit-search
version: 0.2.0
description: Search Reddit for posts and discussions about a topic, with full engagement metadata (upvote count, comment count, author, account standing). Use when the user asks "what does Reddit say about X", "search Reddit for Y", or any time you need community opinions, buying advice, or anecdotal experience from Reddit specifically. Returns normalized JSON sorted by score.
allowed-tools:
  - Bash
triggers:
  - search reddit
  - what does reddit say
  - reddit opinion on
  - reddit thread about
---

# reddit-search

Query Reddit's public JSON endpoint. No auth required.

## When to use

- The user explicitly asks for Reddit results.
- The `/literature-review` orchestrator calls this for purchase/opinion-flavored questions.

Do **not** use this for general web search — call `/web-search` instead.

## How to invoke

Run the bundled script. Pass the query as the first positional arg; optional flags follow.

```bash
${CLAUDE_PLUGIN_ROOT}/skills/reddit-search/scripts/search.sh "<query>" [-s sub1,sub2] [-n LIMIT] [-t hour|day|week|month|year|all] [--user-stats] [--no-fallback]
```

Defaults: `LIMIT=15`, `TIME_WINDOW=all`, no subreddit restriction.

### Common patterns

| Goal | Command |
|---|---|
| Broad search | `search.sh "ergonomic office chair"` |
| Specific subs | `search.sh "office chair" -s buyitforlife,ergonomics` |
| Recent only | `search.sh "M4 macbook" -t month` |
| With community-standing data | `search.sh "tennis elbow" -s redlighttherapy --user-stats` |

### Backends

1. **PullPush (default)** — public Reddit archive at `api.pullpush.io`. Returns full post metadata: score, num_comments, author, author_premium, author_flair, selftext. No auth required.
2. **RSS fallback** — if PullPush returns 0 hits for a specific query (the archive can lag the live site, and very specific queries sometimes miss), the script automatically falls back to Reddit's Atom feed. RSS provides titles, urls, and authors but **no score/comments**.

The output includes `"backend": "pullpush" | "rss"` so downstream consumers know which path produced each item. Use `--no-fallback` to skip RSS and surface "no results" instead.

## Output schema

JSON array; each item:

```json
{
  "source": "reddit",
  "subreddit": "r/buyitforlife",
  "title": "...",
  "url": "https://www.reddit.com/r/.../comments/...",
  "external_url": "https://..." | null,
  "author": "u/...",
  "author_premium": true | false | null,
  "author_flair": "Verified Owner" | null,
  "author_created_utc": 1644360698 | null,
  "author_sub_activity": 7 | null,
  "created_utc": 1730000000,
  "snippet": "first ~400 chars of selftext",
  "score": 412,
  "num_comments": 87,
  "backend": "pullpush" | "rss"
}
```

When you return results to the user, summarize the top items and link the `url`. Do not paste raw JSON unless asked.

## User reliability signals

When determining how much weight to give a Reddit voice, look at:

- **`score` and `num_comments`** — community validation of the specific post.
- **`author_flair`** — non-null flair often indicates community-verified status (e.g. "Verified Owner", "Mod", "Physician"). Highly relevant on niche subs.
- **`author_premium`** — small positive signal (paying users tend to be longer-tenured).
- **`author_created_utc`** — old account = more reputation at stake. Account < 30 days old + posting in their first sub = treat as low-trust.
- **`author_sub_activity`** (only when `--user-stats` is set) — count of submissions by this author in the same subreddit. High count = community member, low/zero = drive-by post.

The `/source-trust` scorer already uses `score` + `num_comments` for its engagement bonus. The other fields are available to the orchestrator (and to you) for additional reasoning when summarizing.

## Failure modes

- **PullPush returns 0:** the archive can lag the live site, and very specific multi-term queries sometimes miss. The script falls back to RSS automatically — you'll see `"backend": "rss"` and `null` engagement counts.
- **HTTP 5xx / timeout:** the script retries once with a 5s backoff. Persistent failure surfaces as `{"errors": [...]}` on stderr with exit code 1.
- **Empty results from both backends:** the query had no hits anywhere — broaden it or drop the subreddit restriction.
- **Python missing:** the script needs `python3` (stdlib only — no pip deps).
