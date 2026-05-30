---
name: academic-search
version: 0.1.0
description: Search peer-reviewed journals and preprints across PubMed (biomedical), Semantic Scholar (cross-disciplinary), OpenAlex (broadest), and arXiv (preprints in CS/physics/q-fin/etc.). Use whenever the user asks a scientific, medical, technical, or evidence-based question — "what does the research say about X", "is Y supported by studies", "find papers on Z", or any domain (medicine, real estate finance, ML, climate) where citation count and study type matter more than Reddit threads. Returns normalized JSON with citation_count, study_type, DOI, journal, authors, abstract.
allowed-tools:
  - Bash
triggers:
  - what does the research say
  - peer reviewed
  - academic papers on
  - pubmed
  - semantic scholar
  - openalex
  - arxiv
  - find studies on
  - is there evidence for
---

# academic-search

Fan out across four free academic search APIs, deduplicate by DOI, return normalized JSON. No auth required for any backend.

## When to use

- The question is scientific / medical / engineering / finance / any field with a peer-reviewed literature.
- The user explicitly mentions journals, papers, studies, or evidence.
- The `/literature-review` orchestrator classifies intent as `scientific` or `medical` (mixed-intent purchase questions where claims matter also benefit — "does red light therapy actually work?" → check the journals, not just Reddit).

Don't use for opinion / lifestyle / purchase-only queries — those are better served by `/reddit-search` + `/web-search`.

## Backend coverage

| Backend | Strength | Auth | Rate limit |
|---|---|---|---|
| **PubMed** (NCBI E-utilities) | Biomedical — MeSH-tagged, explicit study types (RCT, Meta-Analysis, Systematic Review) | None | 3 req/sec |
| **Semantic Scholar** | All disciplines, citation counts + influential-citation flag, abstracts | Optional API key | 1 req/sec without key, 100/sec with |
| **OpenAlex** | Largest index (~250M works), cross-disciplinary citation counts, concept tags, open-access detection | Optional `mailto=` for polite pool | ~10 req/sec |
| **arXiv** | Preprints in physics, CS, math, q-bio, q-fin, stat | None | ~3 req/sec |

**Domain → backend cheat sheet:**

| Domain | Best backends |
|---|---|
| Medicine, health, clinical | `pubmed,openalex,semantic_scholar` |
| Real estate / finance / economics | `openalex,semantic_scholar` (and `arxiv` for q-fin preprints) |
| ML / CS / AI | `arxiv,semantic_scholar,openalex` |
| Physics, math, climate | `arxiv,semantic_scholar,openalex` |
| Engineering, materials | `openalex,semantic_scholar` |
| Cross-disciplinary | all four (default) |

## How to invoke

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/academic-search/scripts/search.py "<query>" \
    [--sources pubmed,semantic_scholar,openalex,arxiv] \
    [-n N] [--year-from YYYY] [--year-to YYYY] \
    [--no-abstracts] \
    [--openalex-mailto EMAIL] [--ss-key KEY]
```

Defaults: all four sources, N=10 per source, no year filter, PubMed fetches abstracts.

### Common patterns

| Goal | Command |
|---|---|
| Recent medical evidence | `search.py "PRP tendinopathy" --sources pubmed --year-from 2022` |
| Real estate finance papers | `search.py "cap rate prediction" --sources openalex,semantic_scholar` |
| ML preprints + published | `search.py "mixture of experts" --sources arxiv,semantic_scholar` |
| Fast scan, no abstracts | `search.py "topic" --no-abstracts -n 5` |

### Optional credentials

- **`SEMANTIC_SCHOLAR_API_KEY`** environment variable — free key from https://www.semanticscholar.org/product/api . Lifts the 1 req/sec limit to 100/sec; recommended for any heavy use.
- **`OPENALEX_MAILTO`** environment variable — your email. OpenAlex puts you in the "polite pool" with faster responses. No registration needed.

## Output schema

JSON array; each item:

```json
{
  "source": "academic:pubmed",
  "title": "...",
  "url": "https://doi.org/10.xxxx/...",
  "external_url": null,
  "authors": ["Author A", "Author B", ...],
  "venue": "Nature Medicine",
  "year": 2024,
  "created_utc": 1704067200,
  "score": 412,                    // citation_count duplicated here so /source-trust's engagement bonus fires
  "num_comments": null,
  "snippet": "abstract text up to ~1200 chars",
  "subreddit": null,
  "doi": "10.1234/...",
  "study_type": "Meta-Analysis | RCT | Review | JournalArticle | Preprint | ...",
  "citation_count": 412,
  "influential_citation_count": 47,
  "open_access_pdf": "https://..." | null,
  "backend": "pubmed" | "semantic_scholar" | "openalex" | "arxiv"
}
```

Records are deduplicated across backends by DOI (preferred) then URL.

## How this composes

- **`/source-trust`** already treats `score` as the engagement signal — academic papers' citation counts flow into trust scoring automatically. Combined with domain prior (`pubmed.ncbi.nlm.nih.gov` = 92, `nature.com` = 95, etc.), a highly cited Nature paper will outrank a Reddit thread on the same topic.
- **`/summarize`** can use `study_type` to weight evidence: prefer Meta-Analysis > Systematic Review > RCT > Cohort > Case Report. The summarizer can also surface the `doi` for citation footnotes and `open_access_pdf` for the user to read in full.
- **`/literature-review`** routes purchase + scientific questions to include academic-search by default.

## Failure modes

- **Semantic Scholar 429:** rate-limited without an API key. The script retries with backoff but may still return empty. Other backends still produce results — verdict downgrades gracefully.
- **OpenAlex empty `abstract_inverted_index`:** some records have no abstract. The `snippet` field stays empty; title + authors + journal still useful.
- **arXiv timezone:** arXiv preprint dates aren't peer-reviewed publication dates — be careful summarizing.
- **PubMed abstract fetch is slow:** use `--no-abstracts` for fast scans, then re-query the top-N with abstracts when you've narrowed down.
- **No DOI in some results:** dedupe falls back to URL match; minor cross-backend overlap may slip through.

## Limitations vs paid scholarly tools

This skill doesn't replicate Web of Science, Scopus, Embase, or Google Scholar's full graph (those have licensed datasets and citation networks). The free APIs cover most published literature but lag commercial indexes by a few weeks and lack some indexing depth. For systematic-review-grade work, run this skill as a first pass and confirm with institutional databases.
