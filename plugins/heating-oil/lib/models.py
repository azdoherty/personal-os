"""Normalized quote shape shared by every source, plus small parsing helpers."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

_LEGAL_SUFFIXES = re.compile(
    r"\b(inc|llc|l\.l\.c|co|corp|corporation|company|ltd)\b\.?", re.I)


@dataclass
class Quote:
    """One dealer's listed price(s). `tiers` maps min-gallons -> $/gal."""
    dealer: str
    tiers: dict[int, float]
    town: str = ""
    phone: str = ""
    url: str = ""
    updated: str | None = None          # ISO date, None if unknown
    sources: list[str] = field(default_factory=list)
    fee: float = 0.0                    # flat delivery/hazmat fee if known
    min_delivery_gallons: int | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tiers"] = {str(k): v for k, v in sorted(self.tiers.items())}
        d["key"] = dealer_key(self.dealer, self.phone)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Quote":
        tiers = d.get("tiers")
        if not tiers and d.get("price") is not None:
            tiers = {d.get("min_gallons", 100): d["price"]}
        if not tiers:
            raise ValueError(f"quote for {d.get('dealer')!r} has no price or tiers")
        updated = d.get("updated")
        return cls(
            dealer=str(d["dealer"]).strip(),
            tiers={int(k): float(v) for k, v in tiers.items()},
            town=d.get("town", "") or "",
            phone=d.get("phone", "") or "",
            url=d.get("url", "") or "",
            updated=(parse_date(updated) if updated else None),
            sources=list(d.get("sources") or ([d["source"]] if d.get("source") else [])),
            fee=float(d.get("fee") or 0.0),
            min_delivery_gallons=d.get("min_delivery_gallons"),
        )


def normalize_name(name: str) -> str:
    n = _LEGAL_SUFFIXES.sub(" ", name.lower().replace("&", " and "))
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    return " ".join(n.split())


def phone_digits(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def dealer_key(name: str, phone: str = "") -> str:
    """Stable identity for a dealer: phone number if we have a full one, else name."""
    return phone_digits(phone) or normalize_name(name)


def parse_price(text: str) -> float | None:
    m = re.search(r"\$?\s*(\d{1,2}\.\d{2,3})\b", text or "")
    if not m:
        return None
    v = float(m.group(1))
    return v if 0.5 <= v <= 15 else None


_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
                 "%b %d, %Y", "%B %d, %Y", "%b %d %Y")


def parse_date(text: str, today: date | None = None) -> str | None:
    """Parse a listing's 'updated' cell to ISO. Year-less 'mm/dd' assumes the most
    recent such date not in the future."""
    t = (text or "").strip()
    if not t:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", t)
    if m:
        today = today or date.today()
        try:
            d = date(today.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
        if d > today:
            d = d.replace(year=today.year - 1)
        return d.isoformat()
    return None
