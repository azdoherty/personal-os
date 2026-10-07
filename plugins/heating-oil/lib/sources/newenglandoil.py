"""newenglandoil.com: COD dealer price listings by state + zone (ME/NH/VT/MA/CT/RI).

Zone pages look like https://www.newenglandoil.com/<state>/zone<N>.asp?x=0 where
<state> is e.g. 'newhampshire'. Which zone covers a ZIP is shown on the site's
state map; setup records the user's zone(s) in config.
"""
from __future__ import annotations

from lib.http import fetch_text
from lib.models import Quote
from lib.sources.html_table import parse_tables

BASE = "https://www.newenglandoil.com"

STATE_SLUGS = {
    "MA": "massachusetts", "RI": "rhodeisland", "NH": "newhampshire",
    "ME": "maine", "VT": "vermont", "CT": "connecticut",
}

# First three ZIP digits -> state, for the states this source covers.
_ZIP3_RANGES = [
    (10, 27, "MA"), (28, 29, "RI"), (30, 38, "NH"),
    (39, 49, "ME"), (50, 59, "VT"), (60, 69, "CT"),
]


def state_for_zip(zip_code: str) -> str | None:
    z3 = int(str(zip_code)[:3])
    for lo, hi, st in _ZIP3_RANGES:
        if lo <= z3 <= hi:
            return st
    return None


def zone_url(state: str, zone: int) -> str:
    slug = STATE_SLUGS.get(state.upper(), state.lower())
    return f"{BASE}/{slug}/zone{zone}.asp?x=0"


def state_index_url(state: str) -> str:
    return f"{BASE}/{STATE_SLUGS.get(state.upper(), state.lower())}/"


def fetch_zone(state: str, zone: int, fetch=fetch_text) -> list[Quote]:
    url = zone_url(state, zone)
    return parse_tables(fetch(url), source=f"newenglandoil:{state.upper()}-zone{zone}",
                        base_url=url)
