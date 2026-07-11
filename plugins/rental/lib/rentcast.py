"""RentCast client. One billable request per property via /avm/rent/long-term,
which returns both a rent estimate and rental comps. The API key travels in the
X-Api-Key header, never in the URL. Responses are cached by address so reruns
within a cycle do not re-spend the 50/month free quota.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from lib.models import Property

BASE_URL = "https://api.rentcast.io/v1"


class RentCastError(Exception):
    pass


class QuotaError(RentCastError):
    pass


def build_rent_url(prop: Property) -> str:
    parts = [prop.address, prop.city, prop.state, prop.zip]
    address = ", ".join(p for p in parts if p)
    params = {"address": address, "propertyType": "Multi-Family"}
    if prop.beds is not None:
        params["bedrooms"] = int(prop.beds)
    if prop.baths is not None:
        params["bathrooms"] = prop.baths
    if prop.sqft is not None:
        params["squareFootage"] = int(prop.sqft)
    return f"{BASE_URL}/avm/rent/long-term?" + urllib.parse.urlencode(params)


def parse_rent_response(data: dict) -> dict:
    comps = []
    for c in data.get("comparables", []) or []:
        comps.append({
            "address": c.get("formattedAddress"),
            "rent": c.get("price"),
            "distance": c.get("distance"),
            "correlation": c.get("correlation"),
        })
    return {
        "rent": data.get("rent"),
        "rent_low": data.get("rentRangeLow"),
        "rent_high": data.get("rentRangeHigh"),
        "comps": comps,
    }


def _http_fetch(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers={
        "X-Api-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "personal-os-rental/0.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise QuotaError(f"RentCast rate/quota limit hit (HTTP 429): {e}") from e
        raise RentCastError(f"RentCast HTTP {e.code}: {e}") from e


def enrich_property(prop: Property, api_key: str, cache: dict,
                    fetcher=_http_fetch) -> Property:
    key = prop.address.strip().lower()
    if key in cache:
        data = cache[key]
    else:
        data = fetcher(build_rent_url(prop), api_key)
        cache[key] = data
    parsed = parse_rent_response(data)
    if parsed["rent"] is not None:
        prop.gross_monthly_rent = float(parsed["rent"])
        prop.rent_source = "rentcast"
    prop.comps = parsed["comps"]
    if not parsed["comps"]:
        prop.notes.append("RentCast returned no rental comps — low confidence")
    return prop
