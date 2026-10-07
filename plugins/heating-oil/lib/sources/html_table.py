"""Header-driven extraction of dealer price tables from arbitrary HTML.

Dealer listing sites change their markup often, so rather than hard-coding cell
positions we find every <table>, map columns by header keywords, and keep rows
that have a dealer name and at least one plausible $/gal price. A price column
whose header names a gallon count ("150+ gal") becomes that volume tier;
otherwise the price is treated as the 100-gallon tier.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from lib.models import Quote, parse_date, parse_price

DEFAULT_TIER = 100

_COLUMN_KEYWORDS = [
    ("dealer", ("company", "dealer", "name", "supplier", "business")),
    ("town", ("town", "city", "location", "area")),
    ("phone", ("phone", "tel", "call")),
    ("updated", ("date", "updated", "posted", "as of")),
    ("price", ("price", "gal", "cash", "cod", "$")),
]


class _TableCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[dict]]] = []
        self._stack: list[list[list[dict]]] = []
        self._row: list[dict] | None = None
        self._cell: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._stack.append([])
        elif tag == "tr" and self._stack:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {"text": "", "href": "", "th": tag == "th"}
        elif tag == "a" and self._cell is not None and not self._cell["href"]:
            self._cell["href"] = a.get("href") or ""
        elif tag == "br" and self._cell is not None:
            self._cell["text"] += " "

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._cell["text"] = " ".join(self._cell["text"].split())
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None and self._stack:
            if self._row:
                self._stack[-1].append(self._row)
            self._row = None
        elif tag == "table" and self._stack:
            self.tables.append(self._stack.pop())

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"] += data


def _classify(header: str) -> str | None:
    h = header.lower()
    for role, words in _COLUMN_KEYWORDS:
        if any(w in h for w in words):
            return role
    return None


def _tier_from_header(header: str) -> int:
    m = re.search(r"(\d{2,4})\s*(\+|-|gal|g\b)", header.lower())
    return int(m.group(1)) if m else DEFAULT_TIER


def _map_columns(header_row: list[dict]) -> dict:
    cols: dict = {"price": []}
    for i, cell in enumerate(header_row):
        role = _classify(cell["text"])
        if role == "price":
            cols["price"].append((i, _tier_from_header(cell["text"])))
        elif role and role not in cols:
            cols[role] = i
    return cols


def parse_tables(html: str, source: str, base_url: str = "") -> list[Quote]:
    p = _TableCollector()
    p.feed(html)
    quotes: list[Quote] = []
    for rows in p.tables:
        header_idx = next((i for i, r in enumerate(rows)
                           if any(_classify(c["text"]) == "price" for c in r)
                           and any(_classify(c["text"]) == "dealer" for c in r)), None)
        if header_idx is None:
            continue
        cols = _map_columns(rows[header_idx])
        if "dealer" not in cols or not cols["price"]:
            continue
        for r in rows[header_idx + 1:]:
            def cell(role):
                i = cols.get(role)
                return r[i] if i is not None and i < len(r) else None
            name_cell = cell("dealer")
            if not name_cell or not name_cell["text"]:
                continue
            tiers = {}
            for i, tier in cols["price"]:
                if i < len(r):
                    v = parse_price(r[i]["text"])
                    if v is not None:
                        tiers[tier] = v
            if not tiers:
                continue
            phone = (cell("phone") or {}).get("text", "")
            if not phone:  # some sites put the phone under the dealer name
                m = re.search(r"\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}", name_cell["text"])
                phone = m.group(0) if m else ""
            name = re.sub(r"\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}", "", name_cell["text"]).strip(" -|")
            href = name_cell["href"]
            if href and base_url and not href.startswith("http"):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            upd = cell("updated")
            quotes.append(Quote(
                dealer=name, tiers=tiers,
                town=(cell("town") or {}).get("text", ""),
                phone=phone, url=href,
                updated=parse_date(upd["text"]) if upd else None,
                sources=[source],
            ))
    return quotes
