#!/usr/bin/env python3
"""academic-search: query peer-reviewed and preprint literature across four free APIs.

Backends:
  - PubMed (NCBI E-utilities) — biomedical, MeSH-tagged, study types
  - Semantic Scholar — cross-disciplinary, citation counts, influential-citations
  - OpenAlex — successor to MAG, broadest coverage, concept tags
  - arXiv — preprints (CS, physics, math, q-bio, q-fin, stat, etc.)

Usage:
  search.py "<query>" [--sources pubmed,semantic_scholar,openalex,arxiv]
                      [-n N] [--year-from YYYY] [--year-to YYYY]
                      [--openalex-mailto EMAIL] [--ss-key KEY]
                      [--no-abstracts]

Output: JSON array on stdout. Normalized fields (compatible with rest of
research plugin), each record includes:
  {
    "source": "academic:<backend>",
    "title": "...",
    "url": "https://doi.org/... | pubmed url | arxiv abs",
    "external_url": null,
    "authors": ["..."],
    "venue": "Nature Medicine",
    "year": 2024,
    "created_utc": <year-jan-1 epoch>,
    "score": <citation_count>,        # so source-trust's engagement bonus fires
    "num_comments": null,
    "snippet": "abstract...",
    "subreddit": null,
    "doi": "10.xxxx/...",
    "study_type": "RCT | meta-analysis | review | ...",
    "citation_count": <int>,
    "influential_citation_count": <int|null>,
    "open_access_pdf": "https://..." | null,
    "backend": "pubmed"|"semantic_scholar"|"openalex"|"arxiv"
  }
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

USER_AGENT = "claude-code-research-plugin/0.5 academic-search"
DEFAULT_LIMIT = 10
DEFAULT_SOURCES = "pubmed,semantic_scholar,openalex,arxiv"


# ---- HTTP helpers --------------------------------------------------------

def fetch(url: str, accept: str = "application/json", attempts: int = 2, backoff: float = 4.0,
          extra_headers: dict | None = None, timeout: int = 25) -> tuple[int, str]:
    """Return (status, body). Status -1 on transport error."""
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    if extra_headers:
        headers.update(extra_headers)
    last_err = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < attempts - 1:
                time.sleep(backoff * (i + 1))
                continue
            return e.code, ""
        except (urllib.error.URLError, OSError, ValueError) as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(backoff)
                continue
    return -1, ""


def year_to_epoch(year: int | None) -> int | None:
    if not year:
        return None
    try:
        return int(datetime(int(year), 1, 1, tzinfo=timezone.utc).timestamp())
    except Exception:  # noqa: BLE001
        return None


# ---- PubMed --------------------------------------------------------------

PUBMED_RCT = "Randomized Controlled Trial"
PUBMED_META = "Meta-Analysis"
PUBMED_SYSREV = "Systematic Review"
PUBMED_REVIEW = "Review"


def _pubmed_study_type(pubtypes: list[str]) -> str | None:
    """Pick the most evidentiary type from PubMed's pubtype list."""
    if not pubtypes:
        return None
    for preferred in (PUBMED_META, PUBMED_SYSREV, PUBMED_RCT, "Clinical Trial",
                      "Practice Guideline", PUBMED_REVIEW, "Comparative Study"):
        for pt in pubtypes:
            if preferred.lower() in pt.lower():
                return preferred
    return pubtypes[0] if pubtypes else None


def pubmed_search(query: str, limit: int, year_from: int | None, year_to: int | None,
                  fetch_abstracts: bool) -> list[dict]:
    q = urllib.parse.quote_plus(query)
    date_filter = ""
    if year_from or year_to:
        yf = year_from or 1900
        yt = year_to or datetime.now(timezone.utc).year
        date_filter = f"&mindate={yf}&maxdate={yt}&datetype=pdat"

    esearch_url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={q}&retmode=json&retmax={limit}&sort=relevance{date_filter}"
    )
    status, body = fetch(esearch_url)
    if status != 200 or not body:
        return []
    try:
        ids = json.loads(body).get("esearchresult", {}).get("idlist", []) or []
    except json.JSONDecodeError:
        return []
    if not ids:
        return []

    esum_url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=pubmed&id={','.join(ids)}&retmode=json"
    )
    status, body = fetch(esum_url)
    if status != 200 or not body:
        return []
    try:
        result = json.loads(body).get("result", {})
    except json.JSONDecodeError:
        return []

    # Optionally fetch abstracts in one call
    abstracts: dict[str, str] = {}
    if fetch_abstracts:
        ef_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={','.join(ids)}&rettype=abstract&retmode=xml"
        )
        status, body = fetch(ef_url, accept="application/xml", timeout=30)
        if status == 200 and body:
            try:
                root = ET.fromstring(body)
                for art in root.findall(".//PubmedArticle"):
                    pmid_el = art.find(".//PMID")
                    if pmid_el is None or not pmid_el.text:
                        continue
                    pmid = pmid_el.text.strip()
                    abs_texts = [
                        (a.text or "").strip()
                        for a in art.findall(".//Abstract/AbstractText")
                    ]
                    if abs_texts:
                        abstracts[pmid] = " ".join(t for t in abs_texts if t)[:1200]
            except ET.ParseError:
                pass

    items: list[dict] = []
    for pmid in ids:
        meta = result.get(pmid)
        if not isinstance(meta, dict):
            continue
        title = (meta.get("title") or "").strip()
        journal = (meta.get("fulljournalname") or meta.get("source") or "").strip()
        year = None
        pubdate = meta.get("pubdate") or ""
        if pubdate:
            m = re.match(r"(\d{4})", pubdate)
            if m:
                year = int(m.group(1))
        authors = [a.get("name") for a in meta.get("authors", []) if isinstance(a, dict)][:8]
        doi = None
        for aid in meta.get("articleids", []):
            if isinstance(aid, dict) and aid.get("idtype") == "doi":
                doi = aid.get("value")
                break
        study_type = _pubmed_study_type(meta.get("pubtype") or [])
        items.append({
            "source": "academic:pubmed",
            "title": title,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "external_url": None,
            "authors": [a for a in authors if a],
            "venue": journal,
            "year": year,
            "created_utc": year_to_epoch(year),
            "score": None,                  # PubMed esummary has no citation count
            "num_comments": None,
            "snippet": abstracts.get(pmid, ""),
            "subreddit": None,
            "doi": doi,
            "study_type": study_type,
            "citation_count": None,
            "influential_citation_count": None,
            "open_access_pdf": None,
            "backend": "pubmed",
        })
    return items


# ---- Semantic Scholar ----------------------------------------------------

SS_FIELDS = ",".join([
    "title", "abstract", "year", "citationCount", "influentialCitationCount",
    "venue", "publicationTypes", "authors.name", "openAccessPdf",
    "externalIds", "publicationDate",
])


def _ss_study_type(ptypes: list[str] | None) -> str | None:
    if not ptypes:
        return None
    for preferred in ("MetaAnalysis", "Review", "JournalArticle", "Editorial",
                      "ClinicalTrial", "CaseReport", "Study"):
        for pt in ptypes:
            if preferred.lower() in (pt or "").lower():
                return preferred
    return ptypes[0] if ptypes else None


def semantic_scholar_search(query: str, limit: int, year_from: int | None, year_to: int | None,
                            api_key: str | None) -> list[dict]:
    q = urllib.parse.quote_plus(query)
    yr = ""
    if year_from or year_to:
        yf = year_from or 1900
        yt = year_to or datetime.now(timezone.utc).year
        yr = f"&year={yf}-{yt}"
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={q}&limit={limit}&fields={SS_FIELDS}{yr}"
    )
    headers = {"x-api-key": api_key} if api_key else None
    status, body = fetch(url, attempts=3, backoff=8.0, extra_headers=headers, timeout=30)
    if status != 200 or not body:
        return []
    try:
        data = json.loads(body).get("data", []) or []
    except json.JSONDecodeError:
        return []
    items = []
    for it in data:
        ext = it.get("externalIds") or {}
        doi = ext.get("DOI")
        pdf = it.get("openAccessPdf") or {}
        year = it.get("year")
        items.append({
            "source": "academic:semantic_scholar",
            "title": (it.get("title") or "").strip(),
            "url": f"https://doi.org/{doi}" if doi else f"https://www.semanticscholar.org/paper/{it.get('paperId','')}",
            "external_url": None,
            "authors": [a.get("name") for a in (it.get("authors") or [])[:8] if isinstance(a, dict) and a.get("name")],
            "venue": (it.get("venue") or "").strip() or None,
            "year": year,
            "created_utc": year_to_epoch(year),
            "score": it.get("citationCount"),
            "num_comments": None,
            "snippet": ((it.get("abstract") or "")[:1200]),
            "subreddit": None,
            "doi": doi,
            "study_type": _ss_study_type(it.get("publicationTypes")),
            "citation_count": it.get("citationCount"),
            "influential_citation_count": it.get("influentialCitationCount"),
            "open_access_pdf": pdf.get("url") if isinstance(pdf, dict) else None,
            "backend": "semantic_scholar",
        })
    return items


# ---- OpenAlex ------------------------------------------------------------

def _openalex_abstract(inv: dict | None) -> str:
    """Reconstruct text from OpenAlex's inverted-index abstract."""
    if not isinstance(inv, dict) or not inv:
        return ""
    positions: list[tuple[int, str]] = []
    for word, indices in inv.items():
        for i in indices:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)[:1200]


_OA_TYPE_MAP = {
    "journal-article": "JournalArticle",
    "review": "Review",
    "book-chapter": "BookChapter",
    "monograph": "Book",
    "report": "Report",
    "dataset": "Dataset",
    "preprint": "Preprint",
}


def openalex_search(query: str, limit: int, year_from: int | None, year_to: int | None,
                    mailto: str | None) -> list[dict]:
    q = urllib.parse.quote_plus(query)
    yr_filter = ""
    if year_from or year_to:
        yf = year_from or 1900
        yt = year_to or datetime.now(timezone.utc).year
        yr_filter = f",publication_year:{yf}-{yt}"
    select = ",".join([
        "id", "doi", "title", "publication_year", "cited_by_count",
        "type", "open_access", "authorships", "primary_location",
        "abstract_inverted_index",
    ])
    url = (
        f"https://api.openalex.org/works?search={q}&per-page={limit}"
        f"&select={select}&filter=type:!paratext{yr_filter}"
    )
    if mailto:
        url += f"&mailto={urllib.parse.quote_plus(mailto)}"
    status, body = fetch(url, timeout=30)
    if status != 200 or not body:
        return []
    try:
        data = json.loads(body).get("results", []) or []
    except json.JSONDecodeError:
        return []
    items = []
    for it in data:
        doi = (it.get("doi") or "").replace("https://doi.org/", "") or None
        oa = it.get("open_access") or {}
        primary = it.get("primary_location") or {}
        venue = ((primary.get("source") or {}) if isinstance(primary, dict) else {}).get("display_name")
        year = it.get("publication_year")
        authors = []
        for a in (it.get("authorships") or [])[:8]:
            if not isinstance(a, dict):
                continue
            au = a.get("author") or {}
            n = au.get("display_name")
            if n:
                authors.append(n)
        oatype = it.get("type") or ""
        items.append({
            "source": "academic:openalex",
            "title": (it.get("title") or "").strip(),
            "url": (f"https://doi.org/{doi}" if doi else it.get("id")),
            "external_url": None,
            "authors": authors,
            "venue": venue,
            "year": year,
            "created_utc": year_to_epoch(year),
            "score": it.get("cited_by_count"),
            "num_comments": None,
            "snippet": _openalex_abstract(it.get("abstract_inverted_index")),
            "subreddit": None,
            "doi": doi,
            "study_type": _OA_TYPE_MAP.get(oatype.lower(), oatype) or None,
            "citation_count": it.get("cited_by_count"),
            "influential_citation_count": None,
            "open_access_pdf": oa.get("oa_url") if isinstance(oa, dict) else None,
            "backend": "openalex",
        })
    return items


# ---- arXiv ---------------------------------------------------------------

ARXIV_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def arxiv_search(query: str, limit: int, year_from: int | None, year_to: int | None) -> list[dict]:
    # arXiv splits on spaces — use quoted phrase to keep multi-word terms together
    if " " in query.strip() and '"' not in query:
        q_term = f'"{query}"'
    else:
        q_term = query
    sq = urllib.parse.quote_plus(f"all:{q_term}")
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query={sq}&max_results={limit}&sortBy=relevance"
    )
    status, body = fetch(url, accept="application/atom+xml", timeout=30)
    if status != 200 or not body:
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    items: list[dict] = []
    for entry in root.findall("a:entry", ARXIV_NS):
        title = (entry.findtext("a:title", "", ARXIV_NS) or "").strip().replace("\n", " ")
        title = re.sub(r"\s+", " ", title)
        summary = (entry.findtext("a:summary", "", ARXIV_NS) or "").strip()
        summary = re.sub(r"\s+", " ", summary)
        pub = entry.findtext("a:published", "", ARXIV_NS) or ""
        year = None
        if pub:
            try:
                year = int(pub[:4])
            except ValueError:
                pass
        if year_from and year and year < year_from:
            continue
        if year_to and year and year > year_to:
            continue
        # Find arXiv abs URL
        arxiv_url = None
        for link in entry.findall("a:link", ARXIV_NS):
            if link.get("type") == "text/html":
                arxiv_url = link.get("href")
                break
        if not arxiv_url:
            arxiv_url = entry.findtext("a:id", "", ARXIV_NS)
        authors = []
        for au in entry.findall("a:author", ARXIV_NS)[:8]:
            n = au.findtext("a:name", "", ARXIV_NS)
            if n:
                authors.append(n.strip())
        # Find DOI if assigned
        doi = entry.findtext("arxiv:doi", default=None, namespaces=ARXIV_NS)
        items.append({
            "source": "academic:arxiv",
            "title": title,
            "url": arxiv_url,
            "external_url": None,
            "authors": authors,
            "venue": "arXiv (preprint)",
            "year": year,
            "created_utc": year_to_epoch(year),
            "score": None,
            "num_comments": None,
            "snippet": summary[:1200],
            "subreddit": None,
            "doi": doi,
            "study_type": "Preprint",
            "citation_count": None,
            "influential_citation_count": None,
            "open_access_pdf": (arxiv_url.replace("/abs/", "/pdf/") + ".pdf") if arxiv_url and "/abs/" in arxiv_url else None,
            "backend": "arxiv",
        })
    return items


# ---- Main ----------------------------------------------------------------

BACKENDS = {
    "pubmed": pubmed_search,
    "semantic_scholar": semantic_scholar_search,
    "openalex": openalex_search,
    "arxiv": arxiv_search,
}


def main() -> int:
    p = argparse.ArgumentParser(description="Search academic literature across PubMed/Semantic Scholar/OpenAlex/arXiv.")
    p.add_argument("query", help="Search query.")
    p.add_argument("--sources", default=DEFAULT_SOURCES,
                   help=f"Comma-separated list. Default: {DEFAULT_SOURCES}.")
    p.add_argument("-n", "--limit", type=int, default=DEFAULT_LIMIT,
                   help=f"Max results per source (default {DEFAULT_LIMIT}).")
    p.add_argument("--year-from", type=int, default=None)
    p.add_argument("--year-to", type=int, default=None)
    p.add_argument("--no-abstracts", action="store_true",
                   help="Skip PubMed efetch (~30% faster, no abstracts).")
    p.add_argument("--openalex-mailto", default=os.environ.get("OPENALEX_MAILTO"),
                   help="Email for OpenAlex polite pool. Env: OPENALEX_MAILTO.")
    p.add_argument("--ss-key", default=os.environ.get("SEMANTIC_SCHOLAR_API_KEY"),
                   help="Semantic Scholar API key. Env: SEMANTIC_SCHOLAR_API_KEY.")
    args = p.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip() in BACKENDS]
    if not sources:
        print(json.dumps({"error": f"no valid sources in {args.sources}"}), file=sys.stderr)
        return 2

    all_items: list[dict] = []
    errors: dict[str, str] = {}
    for src in sources:
        try:
            if src == "pubmed":
                items = pubmed_search(args.query, args.limit, args.year_from, args.year_to,
                                      not args.no_abstracts)
            elif src == "semantic_scholar":
                items = semantic_scholar_search(args.query, args.limit, args.year_from,
                                                args.year_to, args.ss_key)
            elif src == "openalex":
                items = openalex_search(args.query, args.limit, args.year_from, args.year_to,
                                        args.openalex_mailto)
            elif src == "arxiv":
                items = arxiv_search(args.query, args.limit, args.year_from, args.year_to)
            else:
                continue
            all_items.extend(items)
        except Exception as e:  # noqa: BLE001
            errors[src] = str(e)

    # De-dupe by DOI (preferred) then by URL
    seen_doi: set[str] = set()
    seen_url: set[str] = set()
    deduped: list[dict] = []
    for it in all_items:
        doi = (it.get("doi") or "").lower().strip()
        url = (it.get("url") or "").strip()
        if doi and doi in seen_doi:
            continue
        if not doi and url in seen_url:
            continue
        if doi:
            seen_doi.add(doi)
        if url:
            seen_url.add(url)
        deduped.append(it)

    if errors and not deduped:
        print(json.dumps({"errors": errors}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(deduped, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
