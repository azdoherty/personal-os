#!/usr/bin/env bash
# forum-search/hn: query Hacker News via Algolia.
# Usage:
#   hn.sh "<query>" [-n LIMIT] [-t story|comment|all] [-r popularity|recent]
# Output: JSON array of normalized results.
#
# Each item:
#   { "source":"hn", "title":..., "url":..., "external_url":..., "author":...,
#     "created_utc":..., "score":..., "num_comments":..., "snippet":..., "subreddit":null }

set -euo pipefail

QUERY=""
LIMIT=15
TAG="story"
RANK="popularity"  # popularity | recent

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--limit) LIMIT="$2"; shift 2 ;;
    -t|--tags) TAG="$2"; shift 2 ;;
    -r|--rank) RANK="$2"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) if [[ -z "$QUERY" ]]; then QUERY="$1"; else QUERY="$QUERY $1"; fi; shift ;;
  esac
done

if [[ -z "$QUERY" ]]; then
  echo "error: query required" >&2
  exit 2
fi

case "$TAG" in
  story) TAG_FILTER="story" ;;
  comment) TAG_FILTER="comment" ;;
  all) TAG_FILTER="(story,comment)" ;;
  *) echo "error: -t must be story|comment|all" >&2; exit 2 ;;
esac

case "$RANK" in
  popularity) PATH_SEG="search" ;;
  recent) PATH_SEG="search_by_date" ;;
  *) echo "error: -r must be popularity|recent" >&2; exit 2 ;;
esac

ENC_QUERY=$(jq -rn --arg q "$QUERY" '$q|@uri')
URL="https://hn.algolia.com/api/v1/${PATH_SEG}?query=${ENC_QUERY}&tags=${TAG_FILTER}&hitsPerPage=${LIMIT}"

curl -fsSL --max-time 20 "$URL" | jq '[.hits[]? | {
  source: "hn",
  title: (.title // .story_title // (.comment_text // "" | .[0:120])),
  url: ("https://news.ycombinator.com/item?id=" + (.objectID // .story_id|tostring)),
  external_url: .url,
  author: .author,
  created_utc: .created_at_i,
  score: .points,
  num_comments: .num_comments,
  snippet: (.story_text // .comment_text // "" | gsub("<[^>]+>"; " ") | .[0:400]),
  subreddit: null
}]'
