#!/usr/bin/env python3
"""brand-check: score a brand's legitimacy 0-100.

Combines three signals:

  1. Organic Reddit discussion        weight 0.40  (probed via reddit-search.py)
  2. Independent reviewer coverage    weight 0.35  (passed in via --reviewer-hits)
  3. Brand website footprint          weight 0.25  (probed via direct HTTP)

The independent-reviewer signal is passed in rather than fetched because it
requires Claude's WebSearch tool (not available from a shell script). The
companion SKILL.md instructs the orchestrator to gather it and feed it in.

Usage:
  brand_check.py "<brand>" [--reviewer-hits N] [--known-domain DOMAIN]
                          [--reddit-script PATH] [--quick] [--json-only]

Output: JSON on stdout. Schema:
  {
    "brand": "...",
    "legitimacy": 0-100,
    "verdict": "legitimate" | "inconclusive" | "suspicious",
    "signals": [
      {"name": "...", "value": <any>, "weight": <0..1>, "score": 0-100,
       "note": "...", "details": <object|null>}
    ],
    "checked_at": <unix ts>
  }
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

USER_AGENT = "claude-code-research-plugin/0.4 brand-check"

# TLD -> RDAP server. Hardcoded to avoid an extra IANA bootstrap fetch per call.
# rdap.org also handles redirection for most TLDs but lacks .io coverage.
RDAP_BY_TLD = {
    "com": "https://rdap.verisign.com/com/v1/domain/",
    "net": "https://rdap.verisign.com/net/v1/domain/",
    "org": "https://rdap.publicinterestregistry.org/rdap/domain/",
    "io":  "https://rdap.identitydigital.services/rdap/domain/",
    "co":  "https://rdap.identitydigital.services/rdap/domain/",
    "ai":  "https://rdap.identitydigital.services/rdap/domain/",
    "app": "https://www.registry.google/rdap/domain/",
    "dev": "https://www.registry.google/rdap/domain/",
    "shop": "https://rdap.nic.shop/domain/",
    "store": "https://rdap.centralnic.com/store/domain/",
    "info": "https://rdap.afilias.net/rdap/domain/",
    "biz": "https://rdap.nic.biz/domain/",
    "us":  "https://rdap.nic.us/domain/",
    "uk":  "https://rdap.nominet.uk/uk/domain/",
    "ca":  "https://rdap.ca-registry.ca/domain/",
}

# Subreddits where organic recommendations live for product-y purchase queries.
# When checking a brand, hits in these subs are stronger signal than r/all.
ORGANIC_SUBS = [
    "BuyItForLife", "buyitforlife", "ProductRecommendations",
    "Frugal", "Frugalmalefashion", "FemaleFashionAdvice",
    "redlighttherapy", "Tendinitis", "Tendonitis",
    "homegym", "ergonomics", "OfficeChairs",
    "audiophile", "headphones", "watches", "mechanicalkeyboards",
    "EDC", "everydaycarry", "backpacks",
    "running", "cycling", "Sneakers",
]


def fetch_status(url: str, timeout: int = 8) -> tuple[int, str, str]:
    """Return (http_status, body_first_chunk, final_url). Status 0 on error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            chunk = resp.read(20000).decode("utf-8", errors="replace")
            return resp.status, chunk, resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except (urllib.error.URLError, socket.timeout, ConnectionResetError, ValueError):
        return 0, "", url
    except Exception:  # noqa: BLE001
        return 0, "", url


# Domain-parking / for-sale page detectors. These hosts/markers indicate the
# brand doesn't actually own the domain — it's parked, for sale, or expired.
PARKED_HOSTS = {
    "hugedomains.com", "sedo.com", "afternic.com", "dan.com", "buydomains.com",
    "godaddy.com/forsale", "namebright.com", "uniregistry.com",
    "parkingcrew.net", "bodis.com", "fabulous.com", "sav.com",
}
PARKED_MARKERS = (
    "domain is for sale", "buy this domain", "domain for sale",
    "domain parking", "make an offer", "this premium domain",
    "domain name for sale", "expired domain", "the owner of this domain",
    "domain.cfm?d=", "/domain_profile",
)


def is_parked_page(body: str, final_url: str) -> bool:
    final_lc = (final_url or "").lower()
    if any(host in final_lc for host in PARKED_HOSTS):
        return True
    body_lc = (body or "").lower()
    return any(m in body_lc for m in PARKED_MARKERS)


# ---- Signal 1: Reddit organic ---------------------------------------------

def reddit_signal(brand: str, reddit_script: str, quick: bool, keywords: list[str]) -> dict:
    """Probe reddit-search for organic mentions. Returns scored signal dict.

    If `keywords` is non-empty, a hit must also contain at least one keyword
    in its title or snippet — this filters out brand-name collisions (e.g.
    "Lifepro" the wellness brand vs "LifeProTips" the subreddit vs "LifePro
    Leisure Battery" the unrelated battery brand).
    """
    if not os.path.isfile(reddit_script):
        return {
            "name": "reddit_organic",
            "value": None,
            "weight": 0.30,
            "score": 50,
            "note": f"reddit-search.py not found at {reddit_script} — neutral",
            "details": None,
        }

    # Query 1: broad search for the brand name (no sub restriction)
    queries = [
        {"args": [brand], "label": "broad"},
    ]
    if not quick:
        # Query 2: targeted at known organic-recommendation subs
        queries.append(
            {"args": [brand, "-s", ",".join(ORGANIC_SUBS)], "label": "organic_subs"}
        )

    all_hits: list[dict] = []
    errors: list[str] = []
    for q in queries:
        try:
            result = subprocess.run(
                ["python3", reddit_script, *q["args"], "-n", "15", "--no-fallback"],
                capture_output=True,
                text=True,
                timeout=40,
            )
            if result.returncode != 0:
                errors.append(f"{q['label']}: rc={result.returncode}")
                continue
            data = json.loads(result.stdout or "[]")
            if isinstance(data, list):
                all_hits.extend(data)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            errors.append(f"{q['label']}: {e}")

    # Brand-name pattern (word-boundary-ish — letters/digits don't touch the brand)
    pat = re.compile(rf"(?<![a-z0-9]){re.escape(brand.lower())}(?![a-z0-9])")
    # Optional keyword pattern — at least one keyword must appear
    kw_pat = None
    if keywords:
        kw_pat = re.compile(
            r"(?<![a-z0-9])(" + "|".join(re.escape(k.lower()) for k in keywords) + r")(?![a-z0-9])"
        )

    relevant = []
    rejected_collisions = 0
    seen_urls = set()
    for h in all_hits:
        url = h.get("url") or ""
        if url in seen_urls:
            continue
        seen_urls.add(url)
        text = ((h.get("title") or "") + " " + (h.get("snippet") or "")).lower()
        if not pat.search(text):
            continue
        if kw_pat and not kw_pat.search(text):
            rejected_collisions += 1
            continue
        relevant.append(h)

    n = len(relevant)
    total_engagement = sum(
        (h.get("score") or 0) + (h.get("num_comments") or 0) for h in relevant
    )

    if n >= 6 and total_engagement >= 50:
        score, note = 95, f"{n} relevant posts, total engagement {total_engagement}"
    elif n >= 6:
        score, note = 80, f"{n} relevant posts (low engagement)"
    elif n >= 3:
        score, note = 65, f"{n} relevant posts"
    elif n == 2:
        score, note = 45, "2 relevant posts — thin"
    elif n == 1:
        score, note = 25, "1 relevant post — very thin"
    else:
        score, note = 0, "no organic Reddit discussion found"

    if rejected_collisions and kw_pat:
        note += f" ({rejected_collisions} brand-name collisions filtered out by --keywords)"

    return {
        "name": "reddit_organic",
        "value": n,
        "weight": 0.30,
        "score": score,
        "note": note,
        "details": {
            "relevant_posts": n,
            "total_engagement": total_engagement,
            "rejected_collisions": rejected_collisions,
            "keywords_used": keywords or None,
            "errors": errors or None,
            "examples": [
                {"title": h.get("title"), "sub": h.get("subreddit"), "score": h.get("score"), "url": h.get("url")}
                for h in relevant[:3]
            ],
        },
    }


# ---- Signal 2: Independent reviewer (passed in) ---------------------------

def reviewer_signal(reviewer_hits: int) -> dict:
    if reviewer_hits is None or reviewer_hits < 0:
        return {
            "name": "independent_reviewer",
            "value": None,
            "weight": 0.25,
            "score": 50,
            "note": "no reviewer-hits passed in — neutral (use --reviewer-hits)",
            "details": None,
        }
    if reviewer_hits >= 3:
        score, note = 100, f"{reviewer_hits} independent reviewer hits"
    elif reviewer_hits == 2:
        score, note = 75, "2 independent reviewer hits"
    elif reviewer_hits == 1:
        score, note = 50, "1 independent reviewer hit"
    else:
        score, note = 0, "no independent reviewer coverage"
    return {
        "name": "independent_reviewer",
        "value": reviewer_hits,
        "weight": 0.25,
        "score": score,
        "note": note,
        "details": None,
    }


# ---- Signal 4: Domain age (via RDAP) -------------------------------------

def _rdap_url(domain: str) -> str | None:
    domain = domain.lower().strip().lstrip(".").rstrip("/")
    if "/" in domain:
        domain = domain.split("/", 1)[0]
    if "." not in domain:
        return None
    tld = domain.rsplit(".", 1)[-1]
    base = RDAP_BY_TLD.get(tld)
    if base:
        return base + domain
    return f"https://rdap.org/domain/{domain}"


def rdap_lookup(domain: str) -> dict | None:
    url = _rdap_url(domain)
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rdap+json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, json.JSONDecodeError):
        return None
    except Exception:  # noqa: BLE001
        return None


def parse_registration_date(rdap_obj: dict) -> str | None:
    """Find the 'registration' event date in an RDAP response."""
    events = rdap_obj.get("events") or []
    for ev in events:
        action = (ev.get("eventAction") or "").lower()
        if action in ("registration", "registered"):
            return ev.get("eventDate")
    return None


def domain_age_signal(domain: str | None) -> dict:
    """Score: 10+yr=100, 5-10yr=85, 2-5yr=65, 1-2yr=45, 6-12mo=25, <6mo=0."""
    if not domain:
        return {
            "name": "domain_age",
            "value": None,
            "weight": 0.10,
            "score": 50,
            "note": "no domain resolved — neutral",
            "details": None,
        }

    rdap = rdap_lookup(domain)
    if not rdap:
        return {
            "name": "domain_age",
            "value": None,
            "weight": 0.10,
            "score": 50,
            "note": f"RDAP lookup failed for {domain} — neutral",
            "details": None,
        }
    reg_date = parse_registration_date(rdap)
    if not reg_date:
        return {
            "name": "domain_age",
            "value": None,
            "weight": 0.10,
            "score": 50,
            "note": f"RDAP returned no registration event for {domain} — neutral",
            "details": {"events": rdap.get("events")},
        }

    try:
        from datetime import datetime, timezone
        reg = datetime.fromisoformat(reg_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_days = (now - reg).days
    except Exception:  # noqa: BLE001
        return {
            "name": "domain_age",
            "value": None,
            "weight": 0.10,
            "score": 50,
            "note": f"could not parse registration date {reg_date}",
            "details": None,
        }

    years = age_days / 365.25
    if years >= 10:
        score, note = 100, f"{years:.1f} years old"
    elif years >= 5:
        score, note = 85, f"{years:.1f} years old"
    elif years >= 2:
        score, note = 65, f"{years:.1f} years old"
    elif years >= 1:
        score, note = 45, f"{years:.1f} years old — young"
    elif years >= 0.5:
        score, note = 25, f"{age_days} days old — recent"
    else:
        score, note = 0, f"{age_days} days old — very recent (red flag)"

    return {
        "name": "domain_age",
        "value": age_days,
        "weight": 0.10,
        "score": score,
        "note": note,
        "details": {"registration_date": reg_date, "age_years": round(years, 2)},
    }


# ---- Signal 5: Integrity history -----------------------------------------

DEFAULT_CORPUS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "references", "recall_corpus.json",
)


def cpsc_lookup(brand: str, corpus_path: str) -> list[dict]:
    """Return CPSC recall records whose blob mentions the brand (case-insensitive word match)."""
    if not os.path.isfile(corpus_path):
        return []
    try:
        with open(corpus_path, encoding="utf-8") as f:
            corpus = json.load(f)
    except Exception:  # noqa: BLE001
        return []
    brand_lc = brand.lower()
    pat = re.compile(rf"(?<![a-z0-9]){re.escape(brand_lc)}(?![a-z0-9])")
    hits = []
    for rec in corpus.get("records", []):
        blob = rec.get("search_blob") or ""
        if pat.search(blob):
            hits.append({
                "date": rec.get("date"),
                "title": rec.get("title"),
                "url": rec.get("url"),
                "injuries": rec.get("injuries"),
                "hazards": rec.get("hazards"),
                "source": "CPSC",
            })
    return hits


def integrity_signal(integrity_hits: int, brand: str, corpus_path: str) -> dict:
    """Score brand-integrity history. Higher hits = MORE controversies = LOWER score.

    The total hit count is `cpsc_corpus_hits + (integrity_hits or 0)`. The
    corpus lookup catches recalls automatically; --integrity-hits adds
    anything the orchestrator found via WebSearch (lawsuits, FTC actions,
    fabricated endorsements, etc.) that aren't in the CPSC corpus.
    """
    corpus_hits = cpsc_lookup(brand, corpus_path)
    auto_count = len(corpus_hits)
    extra = max(0, integrity_hits or 0) if integrity_hits is not None else None

    if extra is None and auto_count == 0:
        # Neutral case — no auto findings and no manual input
        return {
            "name": "brand_integrity",
            "value": None,
            "weight": 0.20,
            "score": 50,
            "note": "no CPSC recalls found; no --integrity-hits passed — neutral",
            "details": {"cpsc_corpus_hits": []},
        }

    total = auto_count + (extra or 0)
    if total == 0:
        score, note = 100, "no documented controversies (CPSC + WebSearch clean)"
    elif total == 1:
        score, note = 50, "1 documented integrity issue"
    elif total == 2:
        score, note = 20, "2 documented integrity issues — significant concern"
    else:
        score, note = 0, f"{total} documented integrity issues — major red flag"

    if auto_count:
        note += f" (CPSC: {auto_count}, manual: {extra or 0})"

    return {
        "name": "brand_integrity",
        "value": total,
        "weight": 0.20,
        "score": score,
        "note": note,
        "details": {
            "cpsc_corpus_hits": corpus_hits[:5],
            "manual_hits": extra,
        },
    }


# ---- Signal 3: Website footprint ------------------------------------------

def slugify(brand: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "", brand.lower())
    return s


# Hosted e-commerce / site-builder platforms. If we detect one of these in the
# page source, the brand is on a real platform — even if static-HTML markers
# (about/contact/privacy/shop) are masked by JS rendering.
PLATFORM_MARKERS = {
    "shopify": ("cdn.shopify.com", "shopify-section", "shopify.theme", "myshopify.com",
                "/cdn/shop/", "shopify.dispatch"),
    "squarespace": ("static1.squarespace.com", "squarespace-cdn", "y.squarespace",
                    "static.squarespace.com"),
    "wix": ("wixstatic.com", "wixsite.com", "_wix-", "wix-image-kit"),
    "webflow": ("webflow.com", "assets.website-files.com"),
    "bigcommerce": ("bigcommerce.com", "bigcommerce.global", "stencil-utils"),
    "woocommerce": ("woocommerce", "wp-content/plugins/woocommerce"),
}
# Generic e-commerce structure markers
ECOM_STRUCTURE_MARKERS = (
    'og:type" content="product"', '"@type":"product"', '"@type": "product"',
    "/products/", "/collections/", "add to cart", "addtocart", "add-to-cart",
)


def detect_platform(body_lc: str) -> str | None:
    for name, markers in PLATFORM_MARKERS.items():
        if any(m in body_lc for m in markers):
            return name
    return None


def website_signal(brand: str, known_domain: str | None) -> dict:
    """Try common URL patterns. Score on availability + footprint quality."""
    candidates: list[str] = []
    if known_domain:
        candidates.append(known_domain if "://" in known_domain else f"https://{known_domain}")
    slug = slugify(brand)
    if slug:
        for tld in (".com", ".io", ".co", ".net"):
            candidates.append(f"https://{slug}{tld}")
            candidates.append(f"https://www.{slug}{tld}")

    found_url = None
    body = ""
    final_url = ""
    parked_observed: list[dict] = []
    for url in candidates:
        status, chunk, fu = fetch_status(url)
        if status != 200 or not chunk:
            continue
        if is_parked_page(chunk, fu):
            parked_observed.append({"tried": url, "resolved_to": fu})
            continue
        found_url = url
        body = chunk
        final_url = fu
        break

    if not found_url:
        if parked_observed:
            return {
                "name": "website_footprint",
                "value": None,
                "weight": 0.15,
                "score": 0,
                "note": "candidate domain(s) are parked/for-sale — brand does not own them",
                "details": {"parked": parked_observed[:3], "candidates_tried": candidates[:6]},
            }
        return {
            "name": "website_footprint",
            "value": None,
            "weight": 0.15,
            "score": 10,
            "note": "no brand website found at common patterns",
            "details": {"candidates_tried": candidates[:6]},
        }

    body_lc = body.lower()
    platform = detect_platform(body_lc)
    has_ecom_structure = any(m in body_lc for m in ECOM_STRUCTURE_MARKERS)
    footprint_markers = {
        "about": any(k in body_lc for k in ("about us", "/about", ">about<", "our story", "/pages/about")),
        "contact": any(k in body_lc for k in ("contact us", "/contact", ">contact<", "support@", "/pages/contact")),
        "privacy": "/privacy" in body_lc or "privacy policy" in body_lc or "/policies/privacy" in body_lc,
        "shop": (any(k in body_lc for k in ("/shop", "/products", "/collections", "/store"))
                 or has_ecom_structure),
    }
    hits = sum(1 for v in footprint_markers.values() if v)

    # Platform detection acts as a confidence floor: if we know it's a real
    # Shopify/Squarespace/Wix/etc. site, treat partial-marker detections as
    # incomplete parsing rather than evidence of placeholder. Floor at 65.
    if platform and hits >= 2:
        score, note = 100, f"full corporate footprint on {platform} ({hits}/4 markers)"
    elif platform:
        score, note = 75, f"real {platform} site (markers obscured by JS rendering)"
    elif hits >= 3:
        score, note = 100, f"full corporate footprint ({hits}/4 markers)"
    elif hits == 2:
        score, note = 65, f"partial footprint ({hits}/4 markers)"
    elif hits == 1:
        score, note = 35, "minimal site — looks placeholder"
    else:
        score, note = 20, "site responds but no corporate markers"

    return {
        "name": "website_footprint",
        "value": found_url,
        "weight": 0.15,
        "score": score,
        "note": note,
        "details": {
            "url": found_url,
            "platform": platform,
            "markers": footprint_markers,
        },
    }


# ---- Aggregation ----------------------------------------------------------

def aggregate(signals: list[dict]) -> tuple[int, str]:
    total_w = sum(s["weight"] for s in signals)
    if total_w == 0:
        return 50, "inconclusive"
    weighted = sum(s["score"] * s["weight"] for s in signals) / total_w
    legitimacy = int(round(max(0, min(100, weighted))))
    if legitimacy >= 70:
        verdict = "legitimate"
    elif legitimacy >= 40:
        verdict = "inconclusive"
    else:
        verdict = "suspicious"
    return legitimacy, verdict


# ---- Main -----------------------------------------------------------------

DEFAULT_REDDIT_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "reddit-search", "scripts", "search.py",
)


def main() -> int:
    p = argparse.ArgumentParser(description="Score a brand's legitimacy 0-100.")
    p.add_argument("brand", help="Brand name to check (e.g. 'Kineon').")
    p.add_argument(
        "--reviewer-hits",
        type=int,
        default=None,
        help="Number of independent reviewer hits (gathered via WebSearch upstream).",
    )
    p.add_argument(
        "--integrity-hits",
        type=int,
        default=None,
        help="Number of documented integrity issues — recalls, lawsuits, fabricated endorsements, etc. (gathered via WebSearch upstream). 0 = clean, 1+ = concern.",
    )
    p.add_argument(
        "--keywords",
        default="",
        help="Comma-separated category keywords. Reddit hits must contain at least one in addition to the brand name. Filters out brand-name collisions (e.g. 'therapy,vibration,massage' for a wellness brand).",
    )
    p.add_argument(
        "--known-domain",
        default=None,
        help="Skip URL guessing and use this domain directly (e.g. kineon.io).",
    )
    p.add_argument(
        "--reddit-script",
        default=DEFAULT_REDDIT_SCRIPT,
        help="Path to reddit-search/search.py.",
    )
    p.add_argument(
        "--quick",
        action="store_true",
        help="Skip the second Reddit query (organic-subs sweep). Faster, less reliable.",
    )
    p.add_argument(
        "--corpus",
        default=DEFAULT_CORPUS_PATH,
        help="Path to recall_corpus.json (CPSC pre-fetched recalls).",
    )
    args = p.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    # Resolve the website first so its found URL can feed domain-age lookup.
    web_sig = website_signal(args.brand, args.known_domain)
    resolved_domain = None
    if isinstance(web_sig.get("value"), str):
        try:
            host = urllib.parse.urlparse(web_sig["value"]).hostname or ""
            host = host.lower().lstrip(".")
            if host.startswith("www."):
                host = host[4:]
            resolved_domain = host or None
        except Exception:  # noqa: BLE001
            pass
    if not resolved_domain and args.known_domain:
        kd = args.known_domain.lower()
        if "://" in kd:
            kd = urllib.parse.urlparse(kd).hostname or kd
        resolved_domain = (kd or "").lstrip(".")
        if resolved_domain.startswith("www."):
            resolved_domain = resolved_domain[4:]

    signals = [
        reddit_signal(args.brand, os.path.abspath(args.reddit_script), args.quick, keywords),
        reviewer_signal(args.reviewer_hits),
        web_sig,
        domain_age_signal(resolved_domain),
        integrity_signal(args.integrity_hits, args.brand, os.path.abspath(args.corpus)),
    ]
    legitimacy, verdict = aggregate(signals)

    print(
        json.dumps(
            {
                "brand": args.brand,
                "legitimacy": legitimacy,
                "verdict": verdict,
                "signals": signals,
                "checked_at": int(time.time()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
