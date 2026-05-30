#!/usr/bin/env bash
# forum-search/stackexchange: query the StackExchange API.
# Usage:
#   stackexchange.sh "<query>" [-s site] [-n LIMIT]
#   site defaults to stackoverflow. Multiple sites: comma-separated.
#   Common sites: stackoverflow, superuser, askubuntu, serverfault,
#                 cooking, diy, photo, woodworking, parenting, money, gardening.
# Output: JSON array of normalized results.

set -euo pipefail

QUERY=""
SITES="stackoverflow"
LIMIT=15

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--sites) SITES="$2"; shift 2 ;;
    -n|--limit) LIMIT="$2"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) if [[ -z "$QUERY" ]]; then QUERY="$1"; else QUERY="$QUERY $1"; fi; shift ;;
  esac
done

if [[ -z "$QUERY" ]]; then
  echo "error: query required" >&2
  exit 2
fi

ENC_QUERY=$(jq -rn --arg q "$QUERY" '$q|@uri')
RESULTS="[]"

IFS=',' read -ra ARR <<< "$SITES"
for site in "${ARR[@]}"; do
  site_trimmed="${site// /}"
  [[ -z "$site_trimmed" ]] && continue
  URL="https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q=${ENC_QUERY}&site=${site_trimmed}&pagesize=${LIMIT}&filter=withbody"
  if PART=$(curl -fsSL --compressed --max-time 20 "$URL" 2>/dev/null); then
    PART_NORM=$(echo "$PART" | jq --arg site "$site_trimmed" '[.items[]? | {
      source: ("stackexchange:" + $site),
      title: .title,
      url: .link,
      external_url: null,
      author: (.owner.display_name // null),
      created_utc: .creation_date,
      score: .score,
      num_comments: (.answer_count // 0),
      snippet: ((.body // "") | gsub("<[^>]+>"; " ") | gsub("\\s+"; " ") | .[0:400]),
      subreddit: null
    }]')
    RESULTS=$(jq -n --argjson a "$RESULTS" --argjson b "$PART_NORM" '$a + $b')
  fi
done

echo "$RESULTS" | jq --argjson n "$LIMIT" 'sort_by(-(.score // 0)) | .[0:$n]'
