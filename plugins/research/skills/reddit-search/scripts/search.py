#!/usr/bin/env python3
"""reddit-search: query Reddit submissions with full engagement metadata.

Primary backend: api.pullpush.io — a public archive mirror that returns the
full post payload (score, num_comments, author, selftext, flair). No auth
required. Reddit's own JSON endpoints now return 403 for unauthenticated
script traffic, so we route through PullPush instead.

Fallback: Reddit's Atom (RSS) feed. Engagement counts are not exposed in
RSS, but the feed is more current than the PullPush archive, so it's
useful when PullPush returns empty (very recent posts) or errors.

Usage:
  search.py "<query>" [-s sub1,sub2] [-n LIMIT] [-t hour|day|week|month|year|all] [--user-stats] [--no-fallback]

Output: JSON array on stdout. Each item:
  {
    "source": "reddit",
    "subreddit": "r/...",
    "title": "...",
    "url": "https://www.reddit.com/r/.../comments/...",
    "external_url": "https://..." | null,
    "author": "u/...",
    "author_premium": true | false | null,
    "author_flair": "...flair text..." | null,
    "author_sub_activity": <int> | null,  # only when --user-stats is set
    "created_utc": <int>,
    "snippet": "first ~400 chars of selftext (HTML-stripped)",
    "score": <int> | null,
    "num_comments": <int> | null,
    "backend": "pullpush" | "rss"
  }
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

USER_AGENT = "claude-code-research-plugin/0.2 (literature review)"
PULLPUSH_BASE = "https://api.pullpush.io/reddit/search/submission/"
TIME_WINDOWS_S = {
    "hour": 3600,
    "day": 86400,
    "week": 7 * 86400,
    "month": 30 * 86400,
    "year": 365 * 86400,
    "all": None,
}


def fetch(url: str, attempts: int = 2, backoff: float = 5.0, timeout: int = 25) -> str:
    last_err = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if i < attempts - 1:
                time.sleep(backoff)
    raise RuntimeError(f"fetch failed for {url}: {last_err}")


def strip_html(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---- PullPush backend ----------------------------------------------------

def pullpush_search(query: str, subs: list[str], limit: int, time_window: str) -> list[dict]:
    """Return normalized items from PullPush. Empty list if no hits."""
    params: dict[str, str] = {"size": str(min(limit, 100)), "sort": "desc", "sort_type": "score"}
    if query:
        params["q"] = query
    if subs:
        params["subreddit"] = ",".join(subs)
    twin = TIME_WINDOWS_S.get(time_window)
    if twin:
        params["after"] = str(int(time.time()) - twin)

    url = PULLPUSH_BASE + "?" + urllib.parse.urlencode(params)
    raw = fetch(url)
    data = json.loads(raw)
    items = data.get("data", []) or []
    return [normalize_pullpush(it) for it in items]


def normalize_pullpush(it: dict) -> dict:
    permalink = it.get("permalink") or ""
    full_url = (
        "https://www.reddit.com" + permalink if permalink.startswith("/") else (it.get("url") or "")
    )
    raw_url = it.get("url") or ""
    is_self = it.get("is_self", False) or raw_url.startswith("https://www.reddit.com")
    external_url = None if is_self else raw_url
    selftext = it.get("selftext") or ""
    flair_text = it.get("author_flair_text")
    author = it.get("author") or ""
    sub = (it.get("subreddit") or "").lstrip("/")
    if sub.lower().startswith("r/"):
        sub = sub[2:]

    return {
        "source": "reddit",
        "subreddit": ("r/" + sub) if sub else None,
        "title": (it.get("title") or "").strip(),
        "url": full_url,
        "external_url": external_url,
        "author": ("u/" + author) if author and author != "[deleted]" else None,
        "author_premium": it.get("author_premium"),
        "author_flair": flair_text if flair_text else None,
        "author_created_utc": int(it.get("author_created_utc")) if it.get("author_created_utc") else None,
        "author_sub_activity": None,
        "created_utc": int(it.get("created_utc")) if it.get("created_utc") else None,
        "snippet": strip_html(selftext)[:400],
        "score": it.get("score"),
        "num_comments": it.get("num_comments"),
        "backend": "pullpush",
    }


# ---- RSS fallback --------------------------------------------------------

NS = {"atom": "http://www.w3.org/2005/Atom"}


def rss_search(query: str, subs: list[str], limit: int, time_window: str) -> list[dict]:
    q = urllib.parse.quote_plus(query)
    urls = []
    if subs:
        urls = [
            f"https://www.reddit.com/r/{s}/search.rss?q={q}&restrict_sr=1&sort=relevance&t={time_window}&limit={limit}"
            for s in subs
        ]
    else:
        urls = [f"https://www.reddit.com/search.rss?q={q}&sort=relevance&t={time_window}&limit={limit}"]

    all_items: list[dict] = []
    for u in urls:
        try:
            xml_text = fetch(u, timeout=20)
            all_items.extend(parse_rss(xml_text))
        except Exception:  # noqa: BLE001
            continue
    return all_items


def parse_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for entry in root.findall("atom:entry", NS):
        title = (entry.findtext("atom:title", default="", namespaces=NS) or "").strip()
        link_el = entry.find("atom:link", NS)
        url = link_el.get("href") if link_el is not None else ""
        updated = entry.findtext("atom:updated", default="", namespaces=NS) or ""
        raw_author = entry.findtext("atom:author/atom:name", default="", namespaces=NS) or ""
        # RSS emits "/u/name" — normalize to "u/name"
        author = raw_author.lstrip("/")
        cat_el = entry.find("atom:category", NS)
        raw_sub = cat_el.get("label") if cat_el is not None else ""
        # RSS sub label is "r/redlighttherapy" — keep as-is but trim slashes
        sub = (raw_sub or "").lstrip("/")
        content_raw = entry.findtext("atom:content", default="", namespaces=NS) or ""

        snippet = strip_html(content_raw)[:400]

        external_url = None
        for m in re.finditer(r'href="([^"]+)"', content_raw):
            href = html.unescape(m.group(1))
            if href.startswith("http") and "reddit.com" not in href:
                external_url = href
                break

        created_utc = None
        if updated:
            try:
                created_utc = int(
                    datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    .astimezone(timezone.utc)
                    .timestamp()
                )
            except Exception:  # noqa: BLE001
                pass

        items.append(
            {
                "source": "reddit",
                "subreddit": sub or None,
                "title": title,
                "url": url,
                "external_url": external_url,
                "author": author or None,
                "author_premium": None,
                "author_flair": None,
                "author_created_utc": None,
                "author_sub_activity": None,
                "created_utc": created_utc,
                "snippet": snippet,
                "score": None,
                "num_comments": None,
                "backend": "rss",
            }
        )
    return items


# ---- User stats (optional) ----------------------------------------------

def attach_user_stats(items: list[dict]) -> list[dict]:
    """For each unique author, count their submissions in the same subreddit.

    Acts as a community-standing proxy: a user with many posts in r/redlighttherapy
    is more credible on that topic than a one-post tourist.
    """
    def _strip_prefix(value: str, prefix: str) -> str:
        return value[len(prefix):] if value.startswith(prefix) else value

    # group by (author, subreddit)
    pairs = set()
    for it in items:
        a = _strip_prefix((it.get("author") or ""), "u/")
        s = _strip_prefix((it.get("subreddit") or ""), "r/")
        if a and s and a not in ("[deleted]", ""):
            pairs.add((a, s))

    counts: dict[tuple[str, str], int] = {}
    for (a, s) in pairs:
        try:
            url = (
                PULLPUSH_BASE
                + "?"
                + urllib.parse.urlencode({"author": a, "subreddit": s, "size": "100"})
            )
            raw = fetch(url, attempts=1, timeout=15)
            data = json.loads(raw)
            counts[(a, s)] = len(data.get("data", []) or [])
        except Exception:  # noqa: BLE001
            counts[(a, s)] = None  # type: ignore[assignment]

    for it in items:
        a = _strip_prefix((it.get("author") or ""), "u/")
        s = _strip_prefix((it.get("subreddit") or ""), "r/")
        if (a, s) in counts:
            it["author_sub_activity"] = counts[(a, s)]
    return items


# ---- Main ----------------------------------------------------------------

def dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for it in items:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Search Reddit via PullPush archive, with RSS fallback.")
    p.add_argument("query", help="Search query.")
    p.add_argument("-s", "--subs", default="", help="Comma-separated subreddits (no r/ prefix).")
    p.add_argument("-n", "--limit", type=int, default=15, help="Max results (default 15).")
    p.add_argument(
        "-t",
        "--time",
        dest="time_window",
        default="all",
        choices=list(TIME_WINDOWS_S.keys()),
        help="Time window (default all — sorted by score, recency handled downstream by source-trust).",
    )
    p.add_argument(
        "--user-stats",
        action="store_true",
        help="Fetch per-author submission count in the same subreddit (extra API calls).",
    )
    p.add_argument(
        "--no-fallback",
        action="store_true",
        help="Skip the RSS fallback even if PullPush returns nothing.",
    )
    args = p.parse_args()

    def _normalize_sub(s: str) -> str:
        s = s.strip()
        if s.startswith("r/") or s.startswith("R/"):
            s = s[2:]
        return s.lstrip("/")

    subs = [_normalize_sub(s) for s in args.subs.split(",") if s.strip()]
    items: list[dict] = []
    errors: list[str] = []

    # Try PullPush first
    try:
        items = pullpush_search(args.query, subs, args.limit, args.time_window)
    except Exception as e:  # noqa: BLE001
        errors.append(f"pullpush: {e}")

    # Fall back to RSS if PullPush returned nothing
    if not items and not args.no_fallback:
        try:
            items = rss_search(args.query, subs, args.limit, args.time_window)
        except Exception as e:  # noqa: BLE001
            errors.append(f"rss: {e}")

    items = dedupe(items)[: args.limit]

    if args.user_stats and items:
        try:
            items = attach_user_stats(items)
        except Exception as e:  # noqa: BLE001
            errors.append(f"user-stats: {e}")

    if errors and not items:
        print(json.dumps({"errors": errors}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
