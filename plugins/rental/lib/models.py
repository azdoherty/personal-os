"""Normalized data models shared across the rental pipeline.

Every pipeline stage serializes these to JSON on stdout and reads them on stdin.
`from_dict` is tolerant: unknown keys are ignored, missing keys take defaults, so
older/newer stages interoperate.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields


@dataclass
class Unit:
    beds: float | None = None
    baths: float | None = None
    rent: float | None = None  # monthly, USD


@dataclass
class Property:
    address: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    list_price: float = 0.0
    property_type: str = ""
    beds: float | None = None
    baths: float | None = None
    sqft: float | None = None
    year_built: int | None = None
    lot_size: float | None = None
    hoa_monthly: float = 0.0
    latitude: float | None = None
    longitude: float | None = None
    url: str = ""
    mls: str = ""
    days_on_market: int | None = None
    # derived / enrichment
    num_units: int | None = None
    units: list[Unit] = field(default_factory=list)
    gross_monthly_rent: float | None = None
    rent_source: str = ""
    tax_annual: float | None = None
    insurance_annual: float | None = None
    rehab: float = 0.0
    comps: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Property":
        known = {f.name for f in fields(cls)}
        kw = {k: v for k, v in d.items() if k in known and k != "units"}
        units = [Unit(**{k: u.get(k) for k in ("beds", "baths", "rent")})
                 for u in d.get("units", []) or []]
        return cls(units=units, **kw)


@dataclass
class Scenario:
    label: str
    price: float
    monthly_pi: float
    noi_annual: float
    cap_rate: float
    annual_cashflow: float
    cash_on_cash: float
    meets_target: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DealResult:
    property: Property
    scenarios: list[Scenario]
    max_offer_price: float | None
    effective_rate: float
    rank_metric: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "property": self.property.to_dict(),
            "scenarios": [s.to_dict() for s in self.scenarios],
            "max_offer_price": self.max_offer_price,
            "effective_rate": self.effective_rate,
            "rank_metric": self.rank_metric,
            "notes": self.notes,
        }
