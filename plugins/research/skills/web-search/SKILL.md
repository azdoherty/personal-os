---
name: web-search
version: 0.1.0
description: Search the open web (news, blogs, reviews, product pages, official docs) for a topic. Use when the user asks to "search the web", needs current information that isn't on Reddit or HN/StackExchange, wants editorial content (Wirecutter, Consumer Reports, news coverage), or whenever a question requires broad search-engine coverage. Returns normalized JSON.
allowed-tools:
  - WebSearch
  - WebFetch
triggers:
  - search the web for
  - look up
  - find articles about
  - google for
---

# web-search

Wraps Claude's built-in `WebSearch` (and optional `WebFetch` for full-page reads). No API key required.

## When to use

- The user asks for general web results.
- The orchestrator (`/literature-review`) calls this for every question — web search is the broadest baseline source.

Do not use this for Reddit-specific or HN-specific queries — call `/reddit-search` or `/forum-search` instead (they return richer per-source metadata).

## How to invoke

1. Call the `WebSearch` tool with the user's query. Optionally include `allowed_domains` to focus (e.g. `["consumerreports.org", "wirecutter.com", "rtings.com"]` for purchase questions, or `["nature.com", "nih.gov", "arxiv.org"]` for science questions).
2. Take the top N (default 8) results.
3. For up to 3 of the most promising results — i.e. paywall-free, high-trust domains — optionally call `WebFetch` to pull the page body. This is useful when snippets are too short for the summarizer. Skip for paywalled sources (NYT, WSJ, FT) and PDF-heavy pages.
4. Emit normalized JSON.

## Output schema

JSON array; each item:

```json
{
  "source": "web",
  "title": "...",
  "url": "https://...",
  "external_url": null,
  "author": null,
  "created_utc": null,
  "score": null,
  "num_comments": null,
  "snippet": "search-engine snippet OR fetched page summary (~400 chars)",
  "subreddit": null
}
```

## Conventions

- **Domain focus:** when the orchestrator labels the question as `purchase`, prefer `allowed_domains` ∈ {wirecutter, rtings, consumerreports, anandtech, rtings, pcmag, theverge}. For `factual`, prefer official sources (gov, edu, well-known publications). For `opinion`, leave domains open.
- **Recency:** if the question implies "recent" (e.g. mentions a year, "latest", "current"), add the current year to the query.
- **Quote stripping:** do not preserve quotes in queries — they over-constrain and often return zero results.

## Failure modes

- **Empty results:** broaden the query (drop the most specific term) and retry once.
- **WebSearch unavailable:** if the tool errors, fall back to `/reddit-search` + `/forum-search` and note the gap in the final summary.
