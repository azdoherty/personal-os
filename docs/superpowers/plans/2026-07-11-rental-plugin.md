# Rental Multifamily Analysis Plugin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `rental` plugin for the `personal-os` marketplace that turns a Redfin CSV export of local 2–4 unit multifamily listings into a ranked, underwritten shortlist with cash-on-cash returns across price scenarios.

**Architecture:** Composable single-purpose skills (thin CLI wrappers) over a shared, unit-tested stdlib-only Python `lib/` package that holds all real logic. Stages pass normalized JSON on stdin/stdout. A zero-API heuristic screen runs before a human review gate; only survivors consume metered RentCast calls.

**Tech Stack:** Python 3.10+ stdlib only (`dataclasses`, `csv`, `json`, `urllib`, `argparse`, `os`, `pathlib`, `math`). `pytest` for tests. Shell tooling: none required beyond Python. External HTTP: FRED (mortgage benchmark, no key) and RentCast (`X-Api-Key`).

## Global Constraints

- **Stdlib-only Python** — no pip dependencies in any `lib/` or script module. `pytest` is a dev-only tool, never imported by shipped code.
- **Python 3.10+** — `X | None` union syntax and `match` are allowed.
- **Scope filter** — only Redfin `PROPERTY TYPE == "Multi-Family (2-4 Unit)"` rows are analyzed; everything else is dropped at ingest.
- **Secrets never committed** — config lives in the OS config dir, never in the repo. `.gitignore` must exclude `config.local.json` and `*.cache.json`.
- **RentCast** — base URL `https://api.rentcast.io/v1`, auth header `X-Api-Key`, 1 billable request per 200 response, free tier 50/mo. Never put the key in a URL query string.
- **FRED benchmark** — `https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US`, no key, value is a percent (e.g. `6.87` → `0.0687`).
- **Normalized JSON** — every stage reads/writes a JSON array of the shapes defined in Task 2 (`Property.to_dict()` / `DealResult.to_dict()`).
- **Capex rule** — capex is EXCLUDED from NOI/cap rate and subtracted only from cash flow (as a reserve). A `--strict-cashflow` flag drops the reserve from cash flow too.
- **Marketplace validation** — `claude plugin validate plugins/rental` and `claude plugin validate .` must pass after manifest changes.

---

## File Structure

| File | Responsibility |
|---|---|
| `plugins/rental/.claude-plugin/plugin.json` | Plugin manifest |
| `plugins/rental/README.md` | User-facing overview + install |
| `plugins/rental/lib/__init__.py` | Marks `lib` a package (empty) |
| `plugins/rental/lib/models.py` | Dataclasses + JSON (de)serialization |
| `plugins/rental/lib/underwrite.py` | Pure finance engine (payment, returns, scenarios, max offer) |
| `plugins/rental/lib/config.py` | Config path resolution, load/validate/merge, first-run check |
| `plugins/rental/lib/listings.py` | Redfin CSV → `Property[]`, 2–4 unit filter, schema validation |
| `plugins/rental/lib/rates.py` | FRED benchmark fetch + parse + spread + fallback chain |
| `plugins/rental/lib/screen.py` | Heuristic rent, underwrite, threshold filter, rank |
| `plugins/rental/lib/rentcast.py` | RentCast request build + response parse + disk cache |
| `plugins/rental/lib/report.py` | Render markdown + CSV from `DealResult[]` |
| `plugins/rental/references/expense-defaults.json` | Documented default assumption rates |
| `plugins/rental/skills/setup/{SKILL.md,scripts/setup.py}` | Interactive config bootstrap |
| `plugins/rental/skills/ingest-listings/{SKILL.md,scripts/ingest.py}` | CSV → Property JSON |
| `plugins/rental/skills/screen-deals/{SKILL.md,scripts/screen.py}` | Heuristic ranked shortlist |
| `plugins/rental/skills/enrich-rents/{SKILL.md,scripts/enrich.py}` | RentCast enrichment |
| `plugins/rental/skills/report/{SKILL.md,scripts/report.py}` | Report writer |
| `plugins/rental/skills/analyze-rentals/SKILL.md` | Orchestrator prose |
| `plugins/rental/tests/*.py` | Unit tests for the `lib/` core |
| `.claude-plugin/marketplace.json` | Add `rental` entry |
| `.gitignore` | Add config/cache ignores |

**Script→lib bootstrap (used verbatim at the top of every `scripts/*.py`):**

```python
import os, sys
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)
```

---

## Task 1: Plugin scaffold + manifests

**Files:**
- Create: `plugins/rental/.claude-plugin/plugin.json`
- Create: `plugins/rental/lib/__init__.py` (empty)
- Create: `plugins/rental/references/expense-defaults.json`
- Create: `plugins/rental/README.md`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.gitignore`

**Interfaces:**
- Produces: a registered, valid plugin named `rental`; `references/expense-defaults.json` consumed by Task 4 (`config.py`).

- [ ] **Step 1: Create the plugin manifest**

`plugins/rental/.claude-plugin/plugin.json`:
```json
{
  "name": "rental",
  "version": "0.1.0",
  "description": "Analyze local 2-4 unit multifamily listings for long-term rental investment: ingest a Redfin CSV export, screen with a zero-API heuristic, enrich the shortlist with RentCast rent estimates and comps, and report cash-on-cash returns across price scenarios.",
  "author": { "name": "azdoh", "email": "your-email@example.com" }
}
```

- [ ] **Step 2: Create the empty package marker**

`plugins/rental/lib/__init__.py`: empty file.

- [ ] **Step 3: Create documented expense defaults**

`plugins/rental/references/expense-defaults.json`:
```json
{
  "_comment": "Default underwriting assumptions copied into a user's config by the setup skill. Percentages are fractions of GROSS monthly rent unless noted. Edit freely.",
  "financing": {
    "down_payment_pct": 0.25,
    "loan_term_years": 30,
    "closing_cost_pct": 0.03,
    "rate_spread_pct": 0.0075,
    "rate_pin_pct": null
  },
  "expenses": {
    "vacancy_pct": 0.05,
    "maintenance_pct": 0.08,
    "capex_pct": 0.05,
    "management_pct": 0.08,
    "insurance_annual": 1800,
    "landlord_paid_utilities_monthly": 100,
    "property_tax_pct_fallback": 0.02
  },
  "thresholds": {
    "target_coc_pct": 0.08,
    "min_monthly_cashflow": 100,
    "use_one_percent_rule": false
  },
  "screening": {
    "heuristic_rent_mode": "per_sqft",
    "rent_per_sqft": 1.10,
    "rent_per_bedroom": { "1": 850, "2": 1150, "3": 1450 }
  },
  "scenarios": { "price_offsets": [0.0, -0.05, -0.10] }
}
```

- [ ] **Step 4: Create the README**

`plugins/rental/README.md`:
```markdown
# rental

Analyze local **2–4 unit multifamily** listings for long-term rental investment.

## Pipeline

1. `/setup` — one-time: write your market, financing, and expense assumptions to your OS config dir.
2. Export your local for-sale search from Redfin ("Download All" → CSV). Filter the Redfin search to "Multi-family (2-4 Unit)".
3. `/analyze-rentals path/to/redfin.csv` — ingest → heuristic screen → **you prune the shortlist** → RentCast enrichment → markdown + CSV report.

Individual stages are also available: `/ingest-listings`, `/screen-deals`, `/enrich-rents`, `/report`.

## Data sources

- **Redfin CSV export** — free, unlimited local inventory (manual download).
- **RentCast API** — rent estimates + comps + valuations. Free tier is 50 calls/month; the pipeline spends calls only on the shortlist you approve.

## Requirements

- Python 3.10+ (stdlib only).
- A free RentCast API key (https://rentcast.io) for the enrichment step.

## Metrics

Cash-on-cash, cap rate, and NOI are computed per the standard definitions (capex excluded
from NOI, subtracted from cash flow as a reserve). See
`docs/superpowers/specs/2026-07-11-rental-investment-plugin-design.md` for the full model.
```

- [ ] **Step 5: Register the plugin in the marketplace**

In `.claude-plugin/marketplace.json`, add to the `plugins` array (after the `research` entry):
```json
    {
      "name": "rental",
      "description": "Analyze local 2-4 unit multifamily listings for long-term rental investment: Redfin CSV ingest, zero-API heuristic screen, RentCast enrichment, and cash-on-cash reporting across price scenarios.",
      "source": "./plugins/rental",
      "category": "productivity"
    }
```

- [ ] **Step 6: Add config/cache ignores**

Append to `.gitignore`:
```
# rental plugin — never commit local config or cached API responses
config.local.json
*.cache.json
```

- [ ] **Step 7: Validate manifests**

Run: `claude plugin validate plugins/rental && claude plugin validate .`
Expected: both report valid (no errors).

- [ ] **Step 8: Commit**

```bash
git add plugins/rental/.claude-plugin/plugin.json plugins/rental/lib/__init__.py \
        plugins/rental/references/expense-defaults.json plugins/rental/README.md \
        .claude-plugin/marketplace.json .gitignore
git commit -m "feat(rental): scaffold plugin manifest, defaults, marketplace entry"
```

---

## Task 2: Data models (`lib/models.py`)

**Files:**
- Create: `plugins/rental/lib/models.py`
- Test: `plugins/rental/tests/test_models.py`

**Interfaces:**
- Produces:
  - `@dataclass Unit(beds: float|None, baths: float|None, rent: float|None)`
  - `@dataclass Property` with fields: `address:str, city:str, state:str, zip:str, list_price:float, property_type:str, beds:float|None, baths:float|None, sqft:float|None, year_built:int|None, lot_size:float|None, hoa_monthly:float, latitude:float|None, longitude:float|None, url:str, mls:str, days_on_market:int|None, num_units:int|None, units:list[Unit], gross_monthly_rent:float|None, rent_source:str, tax_annual:float|None, insurance_annual:float|None, rehab:float, comps:list[dict], notes:list[str]`
  - `Property.to_dict() -> dict`, `Property.from_dict(d) -> Property`
  - `@dataclass Scenario(label:str, price:float, monthly_pi:float, noi_annual:float, cap_rate:float, annual_cashflow:float, cash_on_cash:float, meets_target:bool)` + `to_dict()`
  - `@dataclass DealResult(property:Property, scenarios:list[Scenario], max_offer_price:float|None, effective_rate:float, rank_metric:float, notes:list[str])` + `to_dict()`
- Consumed by: every other `lib/` module and all scripts.

- [ ] **Step 1: Write the failing test**

`plugins/rental/tests/test_models.py`:
```python
from lib.models import Unit, Property, Scenario, DealResult


def test_property_roundtrip_preserves_fields():
    p = Property(address="123 Main St", city="Springfield", state="IL", zip="62701",
                 list_price=300000.0, property_type="Multi-Family (2-4 Unit)",
                 beds=6, baths=4, sqft=2400, units=[Unit(2, 1, 1200.0)],
                 gross_monthly_rent=2400.0, rent_source="heuristic:per_sqft")
    d = p.to_dict()
    p2 = Property.from_dict(d)
    assert p2.address == "123 Main St"
    assert p2.list_price == 300000.0
    assert p2.units[0].rent == 1200.0
    assert p2.gross_monthly_rent == 2400.0


def test_from_dict_ignores_unknown_keys_and_defaults_missing():
    p = Property.from_dict({"address": "1 A St", "extra_junk": 5})
    assert p.address == "1 A St"
    assert p.list_price == 0.0
    assert p.units == []


def test_dealresult_to_dict_nests_property_and_scenarios():
    p = Property(address="1 A St")
    s = Scenario(label="asking", price=300000.0, monthly_pi=1573.23, noi_annual=13752.0,
                 cap_rate=0.0458, annual_cashflow=-6566.8, cash_on_cash=-0.0782,
                 meets_target=False)
    dr = DealResult(property=p, scenarios=[s], max_offer_price=None,
                    effective_rate=0.0687, rank_metric=-0.0782, notes=[])
    d = dr.to_dict()
    assert d["property"]["address"] == "1 A St"
    assert d["scenarios"][0]["label"] == "asking"
    assert d["max_offer_price"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.models'`.

- [ ] **Step 3: Write minimal implementation**

`plugins/rental/lib/models.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/rental && python -m pytest tests/test_models.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/rental/lib/models.py plugins/rental/tests/test_models.py
git commit -m "feat(rental): add normalized data models with JSON serialization"
```

---

## Task 3: Underwrite engine (`lib/underwrite.py`)

**Files:**
- Create: `plugins/rental/lib/underwrite.py`
- Test: `plugins/rental/tests/test_underwrite.py`

**Interfaces:**
- Consumes: `Property`, `Scenario` from Task 2.
- Produces:
  - `monthly_payment(principal: float, annual_rate: float, term_years: int) -> float`
  - `compute_returns(prop: Property, assumptions: dict, price: float, effective_rate: float, strict_cashflow: bool=False) -> dict` returning keys `monthly_pi, noi_annual, cap_rate, annual_cashflow, cash_on_cash`.
  - `max_offer_price(prop, assumptions, effective_rate, target_coc, strict_cashflow=False) -> float | None`
  - `build_scenarios(prop, assumptions, effective_rate, strict_cashflow=False) -> tuple[list[Scenario], float | None]` (scenarios + max offer price)
- `assumptions` is the merged config dict (see Task 4). Expenses read from `assumptions["expenses"]`, financing from `assumptions["financing"]`, target from `assumptions["thresholds"]["target_coc_pct"]`, offsets from `assumptions["scenarios"]["price_offsets"]`.

- [ ] **Step 1: Write the failing test (hand-computed worked example)**

`plugins/rental/tests/test_underwrite.py`:
```python
import pytest
from lib.models import Property
from lib.underwrite import (
    monthly_payment, compute_returns, max_offer_price, build_scenarios,
)

# Assumptions used across the worked example.
ASSUMPTIONS = {
    "financing": {"down_payment_pct": 0.25, "loan_term_years": 30,
                  "closing_cost_pct": 0.03},
    "expenses": {"vacancy_pct": 0.05, "maintenance_pct": 0.08, "capex_pct": 0.05,
                 "management_pct": 0.08, "insurance_annual": 1800,
                 "landlord_paid_utilities_monthly": 100,
                 "property_tax_pct_fallback": 0.02},
    "thresholds": {"target_coc_pct": 0.08},
    "scenarios": {"price_offsets": [0.0, -0.05, -0.10]},
}


def _duplex():
    # $300k, gross rent $2,400/mo, no tax record -> fallback applies.
    return Property(address="123 Main St", list_price=300000.0,
                    gross_monthly_rent=2400.0)


def test_monthly_payment_matches_amortization_formula():
    # $225k, 7.5%, 30yr -> ~$1,573.23/mo
    assert monthly_payment(225000.0, 0.075, 30) == pytest.approx(1573.23, abs=0.05)


def test_monthly_payment_zero_rate_is_straight_line():
    assert monthly_payment(120000.0, 0.0, 30) == pytest.approx(120000.0 / 360, abs=1e-6)


def test_compute_returns_worked_example():
    r = compute_returns(_duplex(), ASSUMPTIONS, price=300000.0, effective_rate=0.075)
    assert r["monthly_pi"] == pytest.approx(1573.23, abs=0.05)
    assert r["noi_annual"] == pytest.approx(13752.0, abs=0.5)
    assert r["cap_rate"] == pytest.approx(0.04584, abs=0.0002)
    assert r["annual_cashflow"] == pytest.approx(-6566.8, abs=1.0)
    assert r["cash_on_cash"] == pytest.approx(-0.0782, abs=0.0005)


def test_strict_cashflow_adds_back_capex_reserve():
    base = compute_returns(_duplex(), ASSUMPTIONS, 300000.0, 0.075, strict_cashflow=False)
    strict = compute_returns(_duplex(), ASSUMPTIONS, 300000.0, 0.075, strict_cashflow=True)
    # capex reserve = 0.05 * 2400 * 12 = 1440 higher cash flow under strict.
    assert strict["annual_cashflow"] - base["annual_cashflow"] == pytest.approx(1440.0, abs=0.5)


def test_max_offer_price_roundtrips_to_target():
    # A high-rent property so a target of 8% CoC is achievable at some price.
    p = Property(address="X", list_price=200000.0, gross_monthly_rent=3500.0)
    price = max_offer_price(p, ASSUMPTIONS, effective_rate=0.075, target_coc=0.08)
    assert price is not None
    r = compute_returns(p, ASSUMPTIONS, price=price, effective_rate=0.075)
    assert r["cash_on_cash"] == pytest.approx(0.08, abs=0.001)


def test_max_offer_price_none_when_unachievable():
    # Rent so low it doesn't even cover fixed insurance+utilities costs near the
    # search's $10k lower bound, so cash-on-cash is negative there and only gets
    # worse (taxes rise) as price increases -- target is unreachable everywhere.
    p = Property(address="Y", list_price=500000.0, gross_monthly_rent=100.0)
    price = max_offer_price(p, ASSUMPTIONS, effective_rate=0.075, target_coc=0.08)
    assert price is None


def test_build_scenarios_labels_and_flags():
    p = Property(address="X", list_price=200000.0, gross_monthly_rent=3500.0)
    scenarios, max_price = build_scenarios(p, ASSUMPTIONS, effective_rate=0.075)
    assert [s.label for s in scenarios] == ["asking", "-5%", "-10%"]
    assert scenarios[0].price == pytest.approx(200000.0)
    assert scenarios[1].price == pytest.approx(190000.0)
    # meets_target is True only where CoC >= target.
    for s in scenarios:
        assert s.meets_target == (s.cash_on_cash >= 0.08 - 1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_underwrite.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.underwrite'`.

- [ ] **Step 3: Write minimal implementation**

`plugins/rental/lib/underwrite.py`:
```python
"""Pure finance engine. No I/O, no network. All money is monthly unless annual.

Metric definitions (literature-verified):
  EGI  = gross_rent - vacancy
  NOI  = (EGI - operating_expenses) * 12        # excludes capex AND debt service
  cap_rate = NOI / price
  cash_on_cash = (NOI - debt_service - capex_reserve) / cash_invested
Capex is excluded from NOI (it is a capital cost, keeping cap rates financing-neutral)
and subtracted from cash flow as a reserve, unless strict_cashflow drops the reserve.
"""
from __future__ import annotations

from lib.models import Property, Scenario


def monthly_payment(principal: float, annual_rate: float, term_years: int) -> float:
    n = term_years * 12
    if n <= 0:
        return 0.0
    r = annual_rate / 12.0
    if r == 0:
        return principal / n
    factor = r * (1 + r) ** n / ((1 + r) ** n - 1)
    return principal * factor


def _taxes_annual(prop: Property, exp: dict, price: float) -> float:
    if prop.tax_annual is not None:
        return prop.tax_annual
    return price * exp["property_tax_pct_fallback"]


def _insurance_annual(prop: Property, exp: dict) -> float:
    if prop.insurance_annual is not None:
        return prop.insurance_annual
    return exp["insurance_annual"]


def compute_returns(prop: Property, assumptions: dict, price: float,
                    effective_rate: float, strict_cashflow: bool = False) -> dict:
    fin = assumptions["financing"]
    exp = assumptions["expenses"]

    gross_rent = prop.gross_monthly_rent or 0.0
    gross_annual = gross_rent * 12.0
    vacancy_annual = gross_annual * exp["vacancy_pct"]
    egi_annual = gross_annual - vacancy_annual

    op_ex_annual = (
        gross_annual * exp["maintenance_pct"]
        + gross_annual * exp["management_pct"]
        + _taxes_annual(prop, exp, price)
        + _insurance_annual(prop, exp)
        + exp["landlord_paid_utilities_monthly"] * 12.0
    )
    noi_annual = egi_annual - op_ex_annual
    cap_rate = noi_annual / price if price else 0.0

    loan = price * (1 - fin["down_payment_pct"])
    monthly_pi = monthly_payment(loan, effective_rate, fin["loan_term_years"])
    debt_service_annual = monthly_pi * 12.0

    capex_reserve_annual = 0.0 if strict_cashflow else gross_annual * exp["capex_pct"]
    annual_cashflow = noi_annual - debt_service_annual - capex_reserve_annual

    cash_invested = (
        price * fin["down_payment_pct"]
        + price * fin["closing_cost_pct"]
        + (prop.rehab or 0.0)
    )
    cash_on_cash = annual_cashflow / cash_invested if cash_invested else 0.0

    return {
        "monthly_pi": monthly_pi,
        "noi_annual": noi_annual,
        "cap_rate": cap_rate,
        "annual_cashflow": annual_cashflow,
        "cash_on_cash": cash_on_cash,
    }


def max_offer_price(prop: Property, assumptions: dict, effective_rate: float,
                    target_coc: float, strict_cashflow: bool = False,
                    lo: float = 10000.0, hi: float | None = None,
                    tol: float = 1.0) -> float | None:
    """Highest price whose cash-on-cash still meets target_coc.

    cash_on_cash is strictly decreasing in price, so we bisect. Returns None when
    even the lowest bound cannot reach the target (property never cash-flows enough).
    """
    def coc(price: float) -> float:
        return compute_returns(prop, assumptions, price, effective_rate,
                               strict_cashflow)["cash_on_cash"]

    if hi is None:
        hi = max(prop.list_price, lo) * 2.0
    if coc(lo) < target_coc:
        return None          # unachievable even cheap
    if coc(hi) >= target_coc:
        return hi            # target met even at the high bound
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if coc(mid) >= target_coc:
            lo = mid
        else:
            hi = mid
    return lo


def build_scenarios(prop: Property, assumptions: dict, effective_rate: float,
                    strict_cashflow: bool = False) -> tuple[list[Scenario], float | None]:
    target = assumptions["thresholds"]["target_coc_pct"]
    offsets = assumptions["scenarios"]["price_offsets"]
    scenarios: list[Scenario] = []
    for off in offsets:
        price = prop.list_price * (1 + off)
        r = compute_returns(prop, assumptions, price, effective_rate, strict_cashflow)
        label = "asking" if off == 0 else f"{int(round(off * 100))}%"
        scenarios.append(Scenario(
            label=label, price=price, monthly_pi=r["monthly_pi"],
            noi_annual=r["noi_annual"], cap_rate=r["cap_rate"],
            annual_cashflow=r["annual_cashflow"], cash_on_cash=r["cash_on_cash"],
            meets_target=r["cash_on_cash"] >= target - 1e-9,
        ))
    max_price = max_offer_price(prop, assumptions, effective_rate, target, strict_cashflow)
    return scenarios, max_price
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/rental && python -m pytest tests/test_underwrite.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/rental/lib/underwrite.py plugins/rental/tests/test_underwrite.py
git commit -m "feat(rental): add literature-verified underwrite engine"
```

---

## Task 4: Config (`lib/config.py`)

**Files:**
- Create: `plugins/rental/lib/config.py`
- Test: `plugins/rental/tests/test_config.py`

**Interfaces:**
- Consumes: `references/expense-defaults.json` from Task 1.
- Produces:
  - `config_path() -> pathlib.Path` (honors `RENTAL_CONFIG`, else OS config dir)
  - `defaults_path() -> pathlib.Path` (the committed `references/expense-defaults.json`)
  - `load_config() -> dict | None` (None if file absent → first-run)
  - `merge_defaults(user: dict) -> dict` (deep-merge user over defaults)
  - `validate(cfg: dict) -> list[str]` (returns human-readable errors; empty = valid)
  - `load_merged() -> dict` (load + merge + validate; raises `ConfigError` with the joined errors, or `FileNotFoundError` on first-run)
  - `class ConfigError(Exception)`

- [ ] **Step 1: Write the failing test**

`plugins/rental/tests/test_config.py`:
```python
import json
import pytest
from lib import config as cfg


def test_config_path_honors_env(monkeypatch, tmp_path):
    target = tmp_path / "myconfig.json"
    monkeypatch.setenv("RENTAL_CONFIG", str(target))
    assert cfg.config_path() == target


def test_config_path_uses_appdata_on_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("RENTAL_CONFIG", raising=False)
    monkeypatch.setattr(cfg.os, "name", "nt")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = cfg.config_path()
    assert p == tmp_path / "personal-os" / "rental" / "config.json"


def test_load_config_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("RENTAL_CONFIG", str(tmp_path / "nope.json"))
    assert cfg.load_config() is None


def test_merge_defaults_overlays_user_values():
    merged = cfg.merge_defaults({"financing": {"down_payment_pct": 0.20}})
    assert merged["financing"]["down_payment_pct"] == 0.20      # overridden
    assert merged["financing"]["loan_term_years"] == 30          # from defaults
    assert merged["expenses"]["vacancy_pct"] == 0.05             # from defaults


def test_validate_flags_missing_market_and_bad_ranges():
    errors = cfg.validate(cfg.merge_defaults({"financing": {"down_payment_pct": 2.0}}))
    assert any("market" in e for e in errors)          # market required, absent
    assert any("down_payment_pct" in e for e in errors)  # must be 0..1


def test_validate_passes_on_complete_config():
    good = cfg.merge_defaults({
        "market": {"label": "Springfield, IL", "zips": ["62701"]},
        "rentcast_api_key": "test-key",
    })
    assert cfg.validate(good) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.config'`.

- [ ] **Step 3: Write minimal implementation**

`plugins/rental/lib/config.py`:
```python
"""Config location, loading, default-merging, and validation.

Config lives OUTSIDE the repo (it holds an API key + personal assumptions):
  Windows:      %APPDATA%\\personal-os\\rental\\config.json
  macOS/Linux:  ~/.config/personal-os/rental/config.json
Override with the RENTAL_CONFIG env var. Absent file == first run.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path


class ConfigError(Exception):
    pass


def config_path() -> Path:
    override = os.environ.get("RENTAL_CONFIG")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "personal-os" / "rental" / "config.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "personal-os" / "rental" / "config.json"


def defaults_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "expense-defaults.json"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict | None:
    p = config_path()
    if not p.is_file():
        return None
    return _load_json(p)


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def merge_defaults(user: dict) -> dict:
    defaults = {k: v for k, v in _load_json(defaults_path()).items()
                if not k.startswith("_")}
    return _deep_merge(defaults, user or {})


def _in_unit_interval(x) -> bool:
    return isinstance(x, (int, float)) and 0 <= x <= 1


def validate(cfg: dict) -> list[str]:
    errors: list[str] = []
    market = cfg.get("market") or {}
    if not market.get("label"):
        errors.append("market.label is required (e.g. 'Springfield, IL')")
    if not market.get("zips"):
        errors.append("market.zips must list at least one ZIP code")
    if not cfg.get("rentcast_api_key"):
        errors.append("rentcast_api_key is required for the enrichment step")
    fin = cfg.get("financing", {})
    for key in ("down_payment_pct", "closing_cost_pct"):
        if not _in_unit_interval(fin.get(key)):
            errors.append(f"financing.{key} must be a fraction between 0 and 1")
    if not isinstance(fin.get("loan_term_years"), (int, float)) or fin.get("loan_term_years") <= 0:
        errors.append("financing.loan_term_years must be a positive number")
    exp = cfg.get("expenses", {})
    for key in ("vacancy_pct", "maintenance_pct", "capex_pct", "management_pct",
                "property_tax_pct_fallback"):
        if not _in_unit_interval(exp.get(key)):
            errors.append(f"expenses.{key} must be a fraction between 0 and 1")
    return errors


def load_merged() -> dict:
    user = load_config()
    if user is None:
        raise FileNotFoundError(str(config_path()))
    merged = merge_defaults(user)
    errors = validate(merged)
    if errors:
        raise ConfigError("; ".join(errors))
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/rental && python -m pytest tests/test_config.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/rental/lib/config.py plugins/rental/tests/test_config.py
git commit -m "feat(rental): add config resolution, merge, and validation"
```

---

## Task 5: Redfin CSV ingest (`lib/listings.py`)

**Files:**
- Create: `plugins/rental/lib/listings.py`
- Test: `plugins/rental/tests/test_listings.py`
- Test fixture: `plugins/rental/tests/fixtures/redfin_sample.csv`

**Interfaces:**
- Consumes: `Property` from Task 2.
- Produces:
  - `REQUIRED_COLUMNS: list[str]`
  - `MULTIFAMILY_2_4 = "Multi-Family (2-4 Unit)"`
  - `class SchemaError(Exception)`
  - `parse_redfin_csv(text: str) -> tuple[list[Property], dict]` — returns `(properties, stats)` where `stats = {"total": int, "kept": int, "dropped_type": int}`. Raises `SchemaError` listing missing columns.

- [ ] **Step 1: Create the CSV fixture**

`plugins/rental/tests/fixtures/redfin_sample.csv` (header is Redfin's real export header; three data rows — one 2-4 unit, one 5+ unit, one single family):
```csv
SALE TYPE,SOLD DATE,PROPERTY TYPE,ADDRESS,CITY,STATE OR PROVINCE,ZIP OR POSTAL CODE,PRICE,BEDS,BATHS,LOCATION,SQUARE FEET,LOT SIZE,YEAR BUILT,DAYS ON MARKET,$/SQUARE FEET,HOA/MONTH,STATUS,NEXT OPEN HOUSE START TIME,NEXT OPEN HOUSE END TIME,URL,SOURCE,MLS#,FAVORITE,INTERESTED,LATITUDE,LONGITUDE
MLS Listing,,Multi-Family (2-4 Unit),123 Main St,Springfield,IL,62701,300000,6,4,Springfield,2400,5000,1920,14,125,0,Active,,,https://redfin.com/x/1,MLS,MLS-1,N,Y,39.8,-89.65
MLS Listing,,Multi-Family (5+ Unit),9 Big Apts,Springfield,IL,62701,900000,20,12,Springfield,9000,12000,1975,40,100,0,Active,,,https://redfin.com/x/2,MLS,MLS-2,N,Y,39.81,-89.66
MLS Listing,,Single Family Residential,4 Oak Ln,Springfield,IL,62704,220000,3,2,Springfield,1500,7000,2001,7,146,0,Active,,,https://redfin.com/x/3,MLS,MLS-3,N,Y,39.75,-89.7
```

- [ ] **Step 2: Write the failing test**

`plugins/rental/tests/test_listings.py`:
```python
import pathlib
import pytest
from lib.listings import parse_redfin_csv, SchemaError, MULTIFAMILY_2_4

FIX = pathlib.Path(__file__).parent / "fixtures" / "redfin_sample.csv"


def test_parse_keeps_only_2_to_4_unit():
    text = FIX.read_text(encoding="utf-8")
    props, stats = parse_redfin_csv(text)
    assert stats["total"] == 3
    assert stats["kept"] == 1
    assert stats["dropped_type"] == 2
    assert len(props) == 1
    p = props[0]
    assert p.property_type == MULTIFAMILY_2_4
    assert p.address == "123 Main St"
    assert p.zip == "62701"
    assert p.list_price == 300000.0
    assert p.beds == 6
    assert p.sqft == 2400.0
    assert p.year_built == 1920
    assert p.latitude == pytest.approx(39.8)


def test_missing_columns_raise_schema_error():
    with pytest.raises(SchemaError) as e:
        parse_redfin_csv("ADDRESS,PRICE\n1 A St,100000\n")
    assert "PROPERTY TYPE" in str(e.value)


def test_blank_numeric_cells_become_none_not_crash():
    text = ("PROPERTY TYPE,ADDRESS,CITY,STATE OR PROVINCE,ZIP OR POSTAL CODE,PRICE,"
            "BEDS,BATHS,SQUARE FEET,YEAR BUILT,HOA/MONTH,DAYS ON MARKET,URL,MLS#,"
            "LATITUDE,LONGITUDE\n"
            "Multi-Family (2-4 Unit),1 A St,Springfield,IL,62701,250000,,,,,,,,,,\n")
    props, stats = parse_redfin_csv(text)
    assert stats["kept"] == 1
    assert props[0].beds is None
    assert props[0].sqft is None
    assert props[0].list_price == 250000.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_listings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.listings'`.

- [ ] **Step 4: Write minimal implementation**

`plugins/rental/lib/listings.py`:
```python
"""Parse a Redfin CSV export into normalized Property objects, keeping only
2-4 unit multifamily rows (the plugin's scope).

Redfin's 'Download All' export uses a stable header. We validate that the columns
we depend on are present and error clearly (naming the missing ones) rather than
silently producing garbage.
"""
from __future__ import annotations

import csv
import io

from lib.models import Property

MULTIFAMILY_2_4 = "Multi-Family (2-4 Unit)"

REQUIRED_COLUMNS = [
    "PROPERTY TYPE", "ADDRESS", "CITY", "STATE OR PROVINCE",
    "ZIP OR POSTAL CODE", "PRICE",
]


class SchemaError(Exception):
    pass


def _num(row: dict, key: str) -> float | None:
    raw = (row.get(key) or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int(row: dict, key: str) -> int | None:
    v = _num(row, key)
    return int(v) if v is not None else None


def parse_redfin_csv(text: str) -> tuple[list[Property], dict]:
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise SchemaError(
            "Redfin CSV is missing required columns: " + ", ".join(missing)
            + ". Re-export via Redfin's 'Download All' button."
        )

    props: list[Property] = []
    total = dropped_type = 0
    for row in reader:
        total += 1
        if (row.get("PROPERTY TYPE") or "").strip() != MULTIFAMILY_2_4:
            dropped_type += 1
            continue
        props.append(Property(
            address=(row.get("ADDRESS") or "").strip(),
            city=(row.get("CITY") or "").strip(),
            state=(row.get("STATE OR PROVINCE") or "").strip(),
            zip=(row.get("ZIP OR POSTAL CODE") or "").strip(),
            list_price=_num(row, "PRICE") or 0.0,
            property_type=MULTIFAMILY_2_4,
            beds=_num(row, "BEDS"),
            baths=_num(row, "BATHS"),
            sqft=_num(row, "SQUARE FEET"),
            year_built=_int(row, "YEAR BUILT"),
            lot_size=_num(row, "LOT SIZE"),
            hoa_monthly=_num(row, "HOA/MONTH") or 0.0,
            latitude=_num(row, "LATITUDE"),
            longitude=_num(row, "LONGITUDE"),
            url=(row.get("URL") or "").strip(),
            mls=(row.get("MLS#") or "").strip(),
            days_on_market=_int(row, "DAYS ON MARKET"),
        ))
    stats = {"total": total, "kept": len(props), "dropped_type": dropped_type}
    return props, stats
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd plugins/rental && python -m pytest tests/test_listings.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add plugins/rental/lib/listings.py plugins/rental/tests/test_listings.py \
        plugins/rental/tests/fixtures/redfin_sample.csv
git commit -m "feat(rental): add Redfin CSV ingest with 2-4 unit filter"
```

---

## Task 6: Mortgage rate fetch (`lib/rates.py`)

**Files:**
- Create: `plugins/rental/lib/rates.py`
- Test: `plugins/rental/tests/test_rates.py`

**Interfaces:**
- Produces:
  - `FRED_URL: str`
  - `parse_fred_csv(text: str) -> float` — returns the latest benchmark as a fraction (percent/100). Raises `ValueError` if no numeric observation found.
  - `fetch_benchmark(timeout: float = 15.0) -> float` — HTTP GET + parse (network).
  - `effective_rate(cfg: dict) -> tuple[float, str]` — returns `(rate, source_note)`. Uses `financing.rate_pin_pct` if set; else live benchmark + `financing.rate_spread_pct`; on fetch failure falls back to pin, then a labeled default 0.07, surfacing which was used in the note.

- [ ] **Step 1: Write the failing test**

`plugins/rental/tests/test_rates.py`:
```python
import pytest
from lib import rates


SAMPLE_FRED = (
    "observation_date,MORTGAGE30US\n"
    "2026-06-18,6.81\n"
    "2026-06-25,6.87\n"
    "2026-07-02,.\n"          # FRED uses '.' for missing; must be skipped
)


def test_parse_fred_takes_last_numeric_as_fraction():
    assert rates.parse_fred_csv(SAMPLE_FRED) == pytest.approx(0.0687)


def test_parse_fred_raises_on_no_numbers():
    with pytest.raises(ValueError):
        rates.parse_fred_csv("observation_date,MORTGAGE30US\n2026-07-02,.\n")


def test_effective_rate_uses_pin_when_set():
    cfg = {"financing": {"rate_pin_pct": 0.065, "rate_spread_pct": 0.0075}}
    rate, note = rates.effective_rate(cfg)
    assert rate == 0.065
    assert "pin" in note.lower()


def test_effective_rate_adds_spread_to_benchmark(monkeypatch):
    monkeypatch.setattr(rates, "fetch_benchmark", lambda timeout=15.0: 0.0687)
    cfg = {"financing": {"rate_pin_pct": None, "rate_spread_pct": 0.0075}}
    rate, note = rates.effective_rate(cfg)
    assert rate == pytest.approx(0.0762)
    assert "benchmark" in note.lower()


def test_effective_rate_falls_back_on_fetch_failure(monkeypatch):
    def boom(timeout=15.0):
        raise OSError("network down")
    monkeypatch.setattr(rates, "fetch_benchmark", boom)
    cfg = {"financing": {"rate_pin_pct": None, "rate_spread_pct": 0.0075}}
    rate, note = rates.effective_rate(cfg)
    assert rate == pytest.approx(0.07)
    assert "default" in note.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_rates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.rates'`.

- [ ] **Step 3: Write minimal implementation**

`plugins/rental/lib/rates.py`:
```python
"""Fetch the 30-year mortgage benchmark from FRED (no API key) and derive the
effective investment-property rate. Pure parsing is separated from the network
call so it can be unit-tested. All returned rates are fractions (0.0687 == 6.87%).
"""
from __future__ import annotations

import urllib.request

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
_DEFAULT_RATE = 0.07


def parse_fred_csv(text: str) -> float:
    latest: float | None = None
    for line in text.splitlines()[1:]:  # skip header
        parts = line.split(",")
        if len(parts) < 2:
            continue
        raw = parts[1].strip()
        try:
            latest = float(raw) / 100.0
        except ValueError:
            continue  # '.' or blank == missing observation
    if latest is None:
        raise ValueError("No numeric MORTGAGE30US observation found in FRED CSV")
    return latest


def fetch_benchmark(timeout: float = 15.0) -> float:
    req = urllib.request.Request(FRED_URL, headers={"User-Agent": "personal-os-rental/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", "replace")
    return parse_fred_csv(text)


def effective_rate(cfg: dict) -> tuple[float, str]:
    fin = cfg.get("financing", {})
    pin = fin.get("rate_pin_pct")
    spread = fin.get("rate_spread_pct", 0.0)
    if pin is not None:
        return pin, f"pinned rate {pin:.4f} from config"
    try:
        benchmark = fetch_benchmark()
        return benchmark + spread, (
            f"live FRED benchmark {benchmark:.4f} + spread {spread:.4f}"
        )
    except Exception as e:  # noqa: BLE001 - any network/parse failure falls back
        if pin is not None:
            return pin, f"pinned rate (benchmark fetch failed: {e})"
        return _DEFAULT_RATE, (
            f"labeled default {_DEFAULT_RATE:.4f} (benchmark fetch failed: {e})"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/rental && python -m pytest tests/test_rates.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/rental/lib/rates.py plugins/rental/tests/test_rates.py
git commit -m "feat(rental): add FRED benchmark fetch + effective-rate derivation"
```

---

## Task 7: Screening (`lib/screen.py`)

**Files:**
- Create: `plugins/rental/lib/screen.py`
- Test: `plugins/rental/tests/test_screen.py`

**Interfaces:**
- Consumes: `Property` (Task 2), `build_scenarios` (Task 3).
- Produces:
  - `heuristic_rent(prop: Property, screening: dict) -> tuple[float | None, str]` — returns `(monthly_rent, source_note)`. `per_sqft`: `sqft * rent_per_sqft`. `per_bedroom`: `beds` mapped via `rent_per_bedroom` (string keys), capping lookups at the largest table key. Returns `(None, note)` when inputs are missing.
  - `passes_thresholds(returns: dict, gross_rent: float, price: float, thresholds: dict) -> bool` — target CoC (on asking), min monthly cash flow, optional 1% rule.
  - `screen(props: list[Property], cfg: dict, effective_rate: float) -> list[DealResult]` — assigns heuristic rent, builds scenarios, filters by thresholds, returns `DealResult[]` sorted by asking-price cash-on-cash descending. `rank_metric` = asking CoC.

- [ ] **Step 1: Write the failing test**

`plugins/rental/tests/test_screen.py`:
```python
import pytest
from lib.models import Property
from lib import screen

CFG = {
    "financing": {"down_payment_pct": 0.25, "loan_term_years": 30, "closing_cost_pct": 0.03},
    "expenses": {"vacancy_pct": 0.05, "maintenance_pct": 0.08, "capex_pct": 0.05,
                 "management_pct": 0.08, "insurance_annual": 1800,
                 "landlord_paid_utilities_monthly": 100, "property_tax_pct_fallback": 0.02},
    "thresholds": {"target_coc_pct": 0.08, "min_monthly_cashflow": 100,
                   "use_one_percent_rule": False},
    "screening": {"heuristic_rent_mode": "per_sqft", "rent_per_sqft": 1.10,
                  "rent_per_bedroom": {"1": 850, "2": 1150, "3": 1450}},
    "scenarios": {"price_offsets": [0.0, -0.05, -0.10]},
}


def test_heuristic_rent_per_sqft():
    rent, note = screen.heuristic_rent(Property(sqft=2400), CFG["screening"])
    assert rent == pytest.approx(2640.0)     # 2400 * 1.10
    assert "per_sqft" in note


def test_heuristic_rent_per_bedroom_caps_at_largest_key():
    sc = dict(CFG["screening"], heuristic_rent_mode="per_bedroom")
    assert screen.heuristic_rent(Property(beds=2), sc)[0] == pytest.approx(1150.0)
    assert screen.heuristic_rent(Property(beds=8), sc)[0] == pytest.approx(1450.0)  # capped at "3"


def test_heuristic_rent_none_when_input_missing():
    rent, note = screen.heuristic_rent(Property(sqft=None), CFG["screening"])
    assert rent is None


def test_screen_filters_and_ranks_descending():
    good = Property(address="Good", list_price=200000.0, sqft=3600)   # high rent -> passes
    bad = Property(address="Bad", list_price=600000.0, sqft=1200)     # low rent -> fails
    results = screen.screen([good, bad, Property(address="NoData")], CFG, effective_rate=0.07)
    assert [r.property.address for r in results] == ["Good"]
    assert results[0].property.gross_monthly_rent == pytest.approx(3960.0)
    assert results[0].rank_metric == results[0].scenarios[0].cash_on_cash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_screen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.screen'`.

- [ ] **Step 3: Write minimal implementation**

`plugins/rental/lib/screen.py`:
```python
"""Zero-API screening: estimate rent from config heuristics, underwrite, filter by
thresholds, and rank. Runs BEFORE any RentCast call so the user can prune the list.
"""
from __future__ import annotations

from lib.models import Property, DealResult
from lib.underwrite import build_scenarios, compute_returns


def heuristic_rent(prop: Property, screening: dict) -> tuple[float | None, str]:
    mode = screening.get("heuristic_rent_mode", "per_sqft")
    if mode == "per_sqft":
        if prop.sqft:
            return prop.sqft * screening["rent_per_sqft"], "heuristic:per_sqft"
        return None, "heuristic:per_sqft (no sqft)"
    if mode == "per_bedroom":
        table = screening.get("rent_per_bedroom", {})
        if prop.beds is not None and table:
            max_key = max(int(k) for k in table)
            key = str(min(int(prop.beds), max_key))
            return float(table[key]), "heuristic:per_bedroom"
        return None, "heuristic:per_bedroom (no beds)"
    return None, f"heuristic:unknown-mode({mode})"


def passes_thresholds(returns: dict, gross_rent: float, price: float,
                      thresholds: dict) -> bool:
    if returns["cash_on_cash"] < thresholds["target_coc_pct"]:
        return False
    if returns["annual_cashflow"] / 12.0 < thresholds["min_monthly_cashflow"]:
        return False
    if thresholds.get("use_one_percent_rule") and price and gross_rent < 0.01 * price:
        return False
    return True


def screen(props: list[Property], cfg: dict, effective_rate: float) -> list[DealResult]:
    results: list[DealResult] = []
    for prop in props:
        rent, source = heuristic_rent(prop, cfg["screening"])
        if rent is None or not prop.list_price:
            continue
        prop.gross_monthly_rent = rent
        prop.rent_source = source
        asking = compute_returns(prop, cfg, prop.list_price, effective_rate)
        if not passes_thresholds(asking, rent, prop.list_price, cfg["thresholds"]):
            continue
        scenarios, max_price = build_scenarios(prop, cfg, effective_rate)
        results.append(DealResult(
            property=prop, scenarios=scenarios, max_offer_price=max_price,
            effective_rate=effective_rate, rank_metric=asking["cash_on_cash"],
            notes=[f"rent estimated by {source}"],
        ))
    results.sort(key=lambda r: r.rank_metric, reverse=True)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/rental && python -m pytest tests/test_screen.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/rental/lib/screen.py plugins/rental/tests/test_screen.py
git commit -m "feat(rental): add zero-API heuristic screening + ranking"
```

---

## Task 8: RentCast client (`lib/rentcast.py`)

**Files:**
- Create: `plugins/rental/lib/rentcast.py`
- Test: `plugins/rental/tests/test_rentcast.py`

**Interfaces:**
- Consumes: `Property` (Task 2).
- Produces:
  - `BASE_URL = "https://api.rentcast.io/v1"`
  - `class QuotaError(Exception)` / `class RentCastError(Exception)`
  - `build_rent_url(prop: Property) -> str` — `/avm/rent/long-term` with query params (address, propertyType=Multi-Family, bedrooms, bathrooms, squareFootage) URL-encoded. Key is NOT in the URL.
  - `parse_rent_response(data: dict) -> dict` — returns `{"rent": float|None, "rent_low": float|None, "rent_high": float|None, "comps": list[dict]}` (each comp: `address, rent, distance, correlation`).
  - `enrich_property(prop: Property, api_key: str, cache: dict, fetcher=<default http>) -> Property` — mutates+returns prop with `gross_monthly_rent`, `rent_source="rentcast"`, `comps`, and a `notes` entry; uses `cache` dict keyed by address to avoid re-spending. `fetcher(url, api_key) -> dict` is injectable for tests; the default raises `QuotaError` on HTTP 429 and `RentCastError` on other non-200.

- [ ] **Step 1: Write the failing test**

`plugins/rental/tests/test_rentcast.py`:
```python
import pytest
from lib.models import Property
from lib import rentcast

SAMPLE = {
    "rent": 2500, "rentRangeLow": 2300, "rentRangeHigh": 2700,
    "comparables": [
        {"formattedAddress": "1 Cmp St", "price": 2450, "distance": 0.3, "correlation": 0.98},
        {"formattedAddress": "2 Cmp St", "price": 2550, "distance": 0.5, "correlation": 0.95},
    ],
}


def test_build_rent_url_encodes_address_and_omits_key():
    prop = Property(address="123 Main St", city="Springfield", state="IL", zip="62701",
                    beds=6, baths=4, sqft=2400)
    url = rentcast.build_rent_url(prop)
    assert url.startswith("https://api.rentcast.io/v1/avm/rent/long-term?")
    assert "123%20Main%20St" in url or "123+Main+St" in url
    assert "propertyType=Multi-Family" in url
    assert "apikey" not in url.lower() and "api_key" not in url.lower()


def test_parse_rent_response_extracts_estimate_and_comps():
    out = rentcast.parse_rent_response(SAMPLE)
    assert out["rent"] == 2500
    assert out["rent_low"] == 2300
    assert len(out["comps"]) == 2
    assert out["comps"][0]["address"] == "1 Cmp St"
    assert out["comps"][0]["correlation"] == 0.98


def test_enrich_uses_cache_and_sets_rent(monkeypatch):
    calls = {"n": 0}
    def fake_fetch(url, api_key):
        calls["n"] += 1
        return SAMPLE
    prop = Property(address="123 Main St", sqft=2400)
    cache: dict = {}
    rentcast.enrich_property(prop, "key", cache, fetcher=fake_fetch)
    rentcast.enrich_property(prop, "key", cache, fetcher=fake_fetch)  # cached second time
    assert calls["n"] == 1
    assert prop.gross_monthly_rent == 2500
    assert prop.rent_source == "rentcast"
    assert len(prop.comps) == 2


def test_enrich_propagates_quota_error():
    def quota(url, api_key):
        raise rentcast.QuotaError("429")
    with pytest.raises(rentcast.QuotaError):
        rentcast.enrich_property(Property(address="x", sqft=1), "key", {}, fetcher=quota)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_rentcast.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.rentcast'`.

- [ ] **Step 3: Write minimal implementation**

`plugins/rental/lib/rentcast.py`:
```python
"""RentCast client. One billable request per property via /avm/rent/long-term,
which returns both a rent estimate and rental comps. The API key travels in the
X-Api-Key header, never in the URL. Responses are cached by address so reruns
within a cycle do not re-spend the 50/month free quota.
"""
from __future__ import annotations

import json
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
    except urllib.error.HTTPError as e:  # noqa: PERF203
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/rental && python -m pytest tests/test_rentcast.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/rental/lib/rentcast.py plugins/rental/tests/test_rentcast.py
git commit -m "feat(rental): add RentCast client with caching and quota handling"
```

---

## Task 9: Report rendering (`lib/report.py`)

**Files:**
- Create: `plugins/rental/lib/report.py`
- Test: `plugins/rental/tests/test_report.py`

**Interfaces:**
- Consumes: `DealResult` (Task 2).
- Produces:
  - `render_markdown(results: list[DealResult], cfg: dict, rate_note: str) -> str`
  - `render_csv(results: list[DealResult]) -> str` — one row per property: `address, city, zip, list_price, gross_monthly_rent, rent_source, asking_cash_on_cash, asking_cap_rate, asking_monthly_cashflow, max_offer_price, url`.

- [ ] **Step 1: Write the failing test**

`plugins/rental/tests/test_report.py`:
```python
import csv, io
from lib.models import Property, Scenario, DealResult
from lib import report

def _result():
    p = Property(address="123 Main St", city="Springfield", zip="62701",
                 list_price=300000.0, gross_monthly_rent=2400.0, rent_source="rentcast",
                 url="https://redfin.com/x/1")
    s0 = Scenario("asking", 300000.0, 1573.23, 13752.0, 0.0458, -6566.8, -0.0782, False)
    s1 = Scenario("-10%", 270000.0, 1415.9, 13752.0, 0.0509, -4671.0, -0.062, False)
    return DealResult(p, [s0, s1], max_offer_price=None, effective_rate=0.0762,
                      rank_metric=-0.0782, notes=["rent from rentcast"])

def test_markdown_has_headline_table_and_scenarios():
    md = report.render_markdown([_result()], {"market": {"label": "Springfield, IL"}},
                                rate_note="live FRED 0.0687 + spread 0.0075")
    assert "123 Main St" in md
    assert "asking" in md and "-10%" in md
    assert "Cash-on-Cash" in md
    assert "0.0687" in md or "6.87" in md  # rate note surfaced

def test_csv_one_row_per_property_with_asking_metrics():
    text = report.render_csv([_result()])
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 1
    assert rows[0]["address"] == "123 Main St"
    assert rows[0]["asking_cash_on_cash"] == "-0.0782"
    assert rows[0]["max_offer_price"] == ""   # None -> empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/rental && python -m pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.report'`.

- [ ] **Step 3: Write minimal implementation**

`plugins/rental/lib/report.py`:
```python
"""Render DealResult[] to a user-facing markdown report and a machine-readable CSV."""
from __future__ import annotations

import csv
import io

from lib.models import DealResult


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _money(x: float) -> str:
    return f"${x:,.0f}"


def render_markdown(results: list[DealResult], cfg: dict, rate_note: str) -> str:
    market = (cfg.get("market") or {}).get("label", "your market")
    lines = [f"# Rental shortlist — {market}", ""]
    lines.append(f"_Rate basis: {rate_note}. Ranked by cash-on-cash at asking price._")
    lines.append("")
    if not results:
        lines.append("No properties passed screening. Loosen thresholds or widen the search.")
        return "\n".join(lines)

    lines.append("| # | Address | Price | Rent/mo | Asking CoC | Cap rate | Max offer @ target |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        p = r.property
        asking = r.scenarios[0]
        mo = _money(r.max_offer_price) if r.max_offer_price is not None else "—"
        lines.append(
            f"| {i} | {p.address} | {_money(p.list_price)} | {_money(p.gross_monthly_rent or 0)}"
            f" | {_pct(asking.cash_on_cash)} | {_pct(asking.cap_rate)} | {mo} |"
        )
    lines.append("")

    for i, r in enumerate(results, 1):
        p = r.property
        lines.append(f"## {i}. {p.address}, {p.city} {p.zip}")
        lines.append("")
        lines.append(f"- List price: {_money(p.list_price)}")
        lines.append(f"- Estimated gross rent: {_money(p.gross_monthly_rent or 0)}/mo "
                     f"(source: {p.rent_source or 'n/a'})")
        if r.max_offer_price is not None:
            lines.append(f"- **Max offer to hit target: {_money(r.max_offer_price)}**")
        if p.url:
            lines.append(f"- Listing: {p.url}")
        lines.append("")
        lines.append("| Scenario | Price | Monthly P&I | NOI/yr | Cap rate | Cash flow/yr | Cash-on-Cash | Meets target |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for s in r.scenarios:
            lines.append(
                f"| {s.label} | {_money(s.price)} | {_money(s.monthly_pi)} | {_money(s.noi_annual)}"
                f" | {_pct(s.cap_rate)} | {_money(s.annual_cashflow)} | {_pct(s.cash_on_cash)}"
                f" | {'✅' if s.meets_target else '—'} |"
            )
        for note in r.notes:
            lines.append(f"> {note}")
        lines.append("")
    return "\n".join(lines)


def render_csv(results: list[DealResult]) -> str:
    buf = io.StringIO()
    cols = ["address", "city", "zip", "list_price", "gross_monthly_rent", "rent_source",
            "asking_cash_on_cash", "asking_cap_rate", "asking_monthly_cashflow",
            "max_offer_price", "url"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in results:
        p = r.property
        a = r.scenarios[0]
        w.writerow({
            "address": p.address, "city": p.city, "zip": p.zip,
            "list_price": f"{p.list_price:.0f}",
            "gross_monthly_rent": f"{(p.gross_monthly_rent or 0):.0f}",
            "rent_source": p.rent_source,
            "asking_cash_on_cash": f"{a.cash_on_cash:.4f}",
            "asking_cap_rate": f"{a.cap_rate:.4f}",
            "asking_monthly_cashflow": f"{a.annual_cashflow / 12:.0f}",
            "max_offer_price": "" if r.max_offer_price is None else f"{r.max_offer_price:.0f}",
            "url": p.url,
        })
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/rental && python -m pytest tests/test_report.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the whole suite + commit**

Run: `cd plugins/rental && python -m pytest -v`
Expected: all tests pass.
```bash
git add plugins/rental/lib/report.py plugins/rental/tests/test_report.py
git commit -m "feat(rental): add markdown + CSV report rendering"
```

---

## Task 10: `ingest-listings` skill

**Files:**
- Create: `plugins/rental/skills/ingest-listings/SKILL.md`
- Create: `plugins/rental/skills/ingest-listings/scripts/ingest.py`

**Interfaces:**
- Consumes: `parse_redfin_csv` (Task 5).
- Produces: CLI `ingest.py <redfin.csv>` → prints a JSON array of `Property.to_dict()` to stdout; prints stats to stderr.

- [ ] **Step 1: Write the script**

`plugins/rental/skills/ingest-listings/scripts/ingest.py`:
```python
#!/usr/bin/env python3
"""Parse a Redfin CSV export into normalized 2-4 unit Property JSON on stdout."""
import argparse
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.listings import parse_redfin_csv, SchemaError


def main() -> int:
    ap = argparse.ArgumentParser(description="Redfin CSV -> normalized Property JSON")
    ap.add_argument("csv_path", help="Path to a Redfin 'Download All' CSV export")
    args = ap.parse_args()
    with open(args.csv_path, encoding="utf-8") as f:
        text = f.read()
    try:
        props, stats = parse_redfin_csv(text)
    except SchemaError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps([p.to_dict() for p in props], ensure_ascii=False))
    print(f"ingested {stats['kept']}/{stats['total']} rows as 2-4 unit "
          f"({stats['dropped_type']} dropped by property type)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the script end-to-end against the fixture**

Run: `cd plugins/rental && python skills/ingest-listings/scripts/ingest.py tests/fixtures/redfin_sample.csv`
Expected: stdout is a JSON array with exactly one property (`123 Main St`); stderr reads `ingested 1/3 rows as 2-4 unit (2 dropped by property type)`.

- [ ] **Step 3: Write the SKILL.md**

`plugins/rental/skills/ingest-listings/SKILL.md`:
````markdown
---
name: ingest-listings
version: 0.1.0
description: Parse a Redfin CSV export ("Download All") into normalized 2-4 unit multifamily property JSON. Use when the user has a Redfin CSV of local for-sale listings and wants to start the rental-analysis pipeline, or asks to load/ingest listings. Drops everything that is not "Multi-Family (2-4 Unit)".
allowed-tools:
  - Bash
---

# ingest-listings

Turns a Redfin CSV export into the normalized `Property[]` JSON every other rental
skill consumes. Keeps only `PROPERTY TYPE == "Multi-Family (2-4 Unit)"` rows.

## First run

If `~/.config/personal-os/rental/config.json` (or `%APPDATA%\personal-os\rental\config.json`)
does not exist, tell the user to run `/setup` first.

## How to invoke

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ingest-listings/scripts/ingest.py path/to/redfin.csv
```

Stdout is a JSON array of properties; stderr reports how many rows were kept vs dropped.

## Normalized schema

Each item is a `Property`: `address, city, state, zip, list_price, property_type, beds,
baths, sqft, year_built, lot_size, hoa_monthly, latitude, longitude, url, mls,
days_on_market, num_units, units[], gross_monthly_rent, rent_source, tax_annual,
insurance_annual, rehab, comps[], notes[]`. Fields not present in the CSV are null/empty
until a later stage fills them.
````

- [ ] **Step 4: Commit**

```bash
git add plugins/rental/skills/ingest-listings
git commit -m "feat(rental): add ingest-listings skill"
```

---

## Task 11: `screen-deals` skill

**Files:**
- Create: `plugins/rental/skills/screen-deals/SKILL.md`
- Create: `plugins/rental/skills/screen-deals/scripts/screen.py`

**Interfaces:**
- Consumes: `Property.from_dict` (Task 2), `effective_rate` (Task 6), `screen` (Task 7), `load_merged` (Task 4).
- Produces: CLI reading `Property[]` JSON on stdin → `DealResult[]` JSON on stdout.

- [ ] **Step 1: Write the script**

`plugins/rental/skills/screen-deals/scripts/screen.py`:
```python
#!/usr/bin/env python3
"""Read Property[] JSON on stdin, screen with zero-API heuristics, write DealResult[] JSON."""
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.config import load_merged, ConfigError
from lib.models import Property
from lib.rates import effective_rate
from lib.screen import screen


def main() -> int:
    try:
        cfg = load_merged()
    except FileNotFoundError:
        print("error: no config found — run /setup first", file=sys.stderr)
        return 3
    except ConfigError as e:
        print(f"error: invalid config: {e}", file=sys.stderr)
        return 3
    props = [Property.from_dict(d) for d in json.load(sys.stdin)]
    rate, note = effective_rate(cfg)
    results = screen(props, cfg, rate)
    print(json.dumps([r.to_dict() for r in results], ensure_ascii=False))
    print(f"screened {len(props)} -> {len(results)} passed ({note})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify end-to-end (piped from ingest, with a throwaway config)**

Run:
```bash
cd plugins/rental
export RENTAL_CONFIG=$(mktemp)
python3 -c "import json,lib.config as c; d=c.merge_defaults({'market':{'label':'T','zips':['1']},'rentcast_api_key':'k','screening':{'rent_per_sqft':2.0}}); open('$RENTAL_CONFIG','w').write(json.dumps(d))"
python skills/ingest-listings/scripts/ingest.py tests/fixtures/redfin_sample.csv 2>/dev/null \
  | python skills/screen-deals/scripts/screen.py
```
Expected: stdout is a JSON array (0+ `DealResult`s depending on the numbers); stderr shows `screened 1 -> N passed (...)`. No traceback.

- [ ] **Step 3: Write the SKILL.md**

`plugins/rental/skills/screen-deals/SKILL.md`:
````markdown
---
name: screen-deals
version: 0.1.0
description: Screen normalized 2-4 unit property JSON with a zero-API rent heuristic, underwrite each, filter by your configured thresholds, and rank by cash-on-cash. Use after ingest-listings and BEFORE spending any RentCast calls, so the user can review and prune the shortlist. Reads Property[] JSON on stdin, writes ranked DealResult[] JSON.
allowed-tools:
  - Bash
---

# screen-deals

Zero-API screening. Estimates rent from config heuristics (no network), underwrites every
property, keeps those meeting your thresholds, and ranks by cash-on-cash.

## Invoke

```bash
cat properties.json | python3 ${CLAUDE_PLUGIN_ROOT}/skills/screen-deals/scripts/screen.py
```

## IMPORTANT: human review gate

After running this, **present the ranked shortlist to the user and let them prune it**
before any RentCast enrichment. Screening spends no API calls; enrichment does. Pass only
the properties the user keeps to `/enrich-rents`.
````

- [ ] **Step 4: Commit**

```bash
git add plugins/rental/skills/screen-deals
git commit -m "feat(rental): add screen-deals skill with human review gate"
```

---

## Task 12: `enrich-rents` skill

**Files:**
- Create: `plugins/rental/skills/enrich-rents/SKILL.md`
- Create: `plugins/rental/skills/enrich-rents/scripts/enrich.py`

**Interfaces:**
- Consumes: `Property.from_dict` (Task 2), `enrich_property`, `QuotaError` (Task 8), `load_merged` (Task 4). Cache file: `<cwd>/rentcast.cache.json` (gitignored by `*.cache.json`).
- Produces: CLI reading `Property[]` JSON on stdin → enriched `Property[]` JSON on stdout. On quota exhaustion, emits what it has and exits non-zero.

- [ ] **Step 1: Write the script**

`plugins/rental/skills/enrich-rents/scripts/enrich.py`:
```python
#!/usr/bin/env python3
"""Enrich a pruned Property[] with RentCast rent estimates + comps. Metered: one
RentCast call per uncached property. Reads/writes the pruned list as JSON."""
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.config import load_merged, ConfigError
from lib.models import Property
from lib.rentcast import enrich_property, QuotaError, RentCastError

CACHE_PATH = os.path.join(os.getcwd(), "rentcast.cache.json")


def _load_cache() -> dict:
    if os.path.isfile(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def main() -> int:
    try:
        cfg = load_merged()
    except FileNotFoundError:
        print("error: no config found — run /setup first", file=sys.stderr)
        return 3
    except ConfigError as e:
        print(f"error: invalid config: {e}", file=sys.stderr)
        return 3
    api_key = cfg["rentcast_api_key"]
    props = [Property.from_dict(d) for d in json.load(sys.stdin)]
    cache = _load_cache()
    enriched, spent = [], 0
    exit_code = 0
    for prop in props:
        before = len(cache)
        try:
            enrich_property(prop, api_key, cache)
            spent += (len(cache) - before)
        except QuotaError as e:
            prop.notes.append(f"not enriched: {e}")
            print(f"warning: RentCast quota/limit reached after {spent} calls; "
                  f"stopping enrichment. Remaining properties left un-enriched.",
                  file=sys.stderr)
            enriched.append(prop)
            exit_code = 4
            break
        except RentCastError as e:
            prop.notes.append(f"enrichment failed: {e}")
        enriched.append(prop)
    # append any properties after a quota break, un-enriched
    seen = {id(p) for p in enriched}
    for prop in props:
        if id(prop) not in seen:
            enriched.append(prop)
    _save_cache(cache)
    print(json.dumps([p.to_dict() for p in enriched], ensure_ascii=False))
    print(f"enriched with {spent} RentCast call(s); cache at {CACHE_PATH}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the no-network paths (config-missing + empty input)**

Run: `cd plugins/rental && echo "[]" | RENTAL_CONFIG=/nonexistent/x.json python skills/enrich-rents/scripts/enrich.py; echo "exit=$?"`
Expected: stderr `error: no config found — run /setup first`, `exit=3`. (Live RentCast calls are not tested here — they require a real key.)

- [ ] **Step 3: Write the SKILL.md**

`plugins/rental/skills/enrich-rents/SKILL.md`:
````markdown
---
name: enrich-rents
version: 0.1.0
description: Enrich a PRUNED shortlist of 2-4 unit properties with real RentCast rent estimates and rental comps. Metered — spends one RentCast API call per property (free tier is 50/month), so only run this on the properties the user kept after screen-deals. Reads Property[] JSON on stdin, writes enriched Property[] JSON. Caches responses to avoid re-spending.
allowed-tools:
  - Bash
---

# enrich-rents

Replaces the screening heuristic rent with a real RentCast estimate + comps, for the
properties the user kept at the review gate.

## Cost

One billable RentCast call per uncached property (`/avm/rent/long-term` returns rent +
comps together). Free tier is 50 calls/month. Responses cache to `rentcast.cache.json`
in the working directory, so reruns within a cycle do not re-spend.

## Invoke (only on the pruned list)

```bash
cat pruned.json | python3 ${CLAUDE_PLUGIN_ROOT}/skills/enrich-rents/scripts/enrich.py > enriched.json
```

If the quota is exhausted mid-run the script stops, emits what it has, notes the rest as
un-enriched, and exits 4. Report that to the user rather than silently dropping properties.
````

- [ ] **Step 4: Commit**

```bash
git add plugins/rental/skills/enrich-rents
git commit -m "feat(rental): add enrich-rents skill (metered RentCast step)"
```

---

## Task 13: `report` skill

**Files:**
- Create: `plugins/rental/skills/report/SKILL.md`
- Create: `plugins/rental/skills/report/scripts/report.py`

**Interfaces:**
- Consumes: enriched `Property[]` JSON on stdin, `build_scenarios` (Task 3), `effective_rate` (Task 6), `render_markdown`/`render_csv` (Task 9), `load_merged` (Task 4).
- Produces: writes `rental-report.md` + `rental-report.csv` to `--out-dir` (default cwd); prints the markdown to stdout.

- [ ] **Step 1: Write the script**

`plugins/rental/skills/report/scripts/report.py`:
```python
#!/usr/bin/env python3
"""Read enriched Property[] JSON on stdin, re-underwrite with real rents + live rate,
and write a ranked markdown report + CSV."""
import argparse
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.config import load_merged, ConfigError
from lib.models import Property, DealResult
from lib.rates import effective_rate
from lib.underwrite import build_scenarios, compute_returns
from lib.report import render_markdown, render_csv


def main() -> int:
    ap = argparse.ArgumentParser(description="Render rental report from enriched JSON")
    ap.add_argument("--out-dir", default=os.getcwd())
    ap.add_argument("--strict-cashflow", action="store_true")
    args = ap.parse_args()
    try:
        cfg = load_merged()
    except FileNotFoundError:
        print("error: no config found — run /setup first", file=sys.stderr)
        return 3
    except ConfigError as e:
        print(f"error: invalid config: {e}", file=sys.stderr)
        return 3

    props = [Property.from_dict(d) for d in json.load(sys.stdin)]
    rate, note = effective_rate(cfg)
    results = []
    for p in props:
        if not (p.gross_monthly_rent and p.list_price):
            continue
        scenarios, max_price = build_scenarios(p, cfg, rate, args.strict_cashflow)
        asking = compute_returns(p, cfg, p.list_price, rate, args.strict_cashflow)
        results.append(DealResult(p, scenarios, max_price, rate,
                                  rank_metric=asking["cash_on_cash"], notes=list(p.notes)))
    results.sort(key=lambda r: r.rank_metric, reverse=True)

    md = render_markdown(results, cfg, note)
    csv_text = render_csv(results)
    md_path = os.path.join(args.out_dir, "rental-report.md")
    csv_path = os.path.join(args.out_dir, "rental-report.csv")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_text)
    print(md)
    print(f"wrote {md_path} and {csv_path} ({len(results)} properties)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify end-to-end with a hand-made enriched record**

Run:
```bash
cd plugins/rental
export RENTAL_CONFIG=$(mktemp)
python3 -c "import json,lib.config as c; open('$RENTAL_CONFIG','w').write(json.dumps(c.merge_defaults({'market':{'label':'T','zips':['1']},'rentcast_api_key':'k'})))"
echo '[{"address":"1 A St","list_price":200000,"gross_monthly_rent":3500,"rent_source":"rentcast"}]' \
  | python skills/report/scripts/report.py --out-dir "$(mktemp -d)"
```
Expected: markdown prints to stdout with a scenario table; stderr notes the two files written. No traceback.

- [ ] **Step 3: Write the SKILL.md**

`plugins/rental/skills/report/SKILL.md`:
````markdown
---
name: report
version: 0.1.0
description: Render a ranked markdown report plus a CSV export from enriched 2-4 unit property JSON. Re-underwrites each property with its real rent and the live mortgage rate, producing per-property cash-on-cash scenario tables (asking / -5% / -10%) and the max offer price to hit your target return. Use as the final step of the rental pipeline. Reads Property[] JSON on stdin.
allowed-tools:
  - Bash
---

# report

Final stage. Reads enriched `Property[]` JSON, re-underwrites with real rents + the live
rate, and writes `rental-report.md` and `rental-report.csv`.

## Invoke

```bash
cat enriched.json | python3 ${CLAUDE_PLUGIN_ROOT}/skills/report/scripts/report.py --out-dir .
```

- `--strict-cashflow` drops the capex reserve from cash flow (pure textbook figure).

The markdown has a headline ranking table then one section per property with a
scenario table (price, P&I, NOI, cap rate, cash flow, cash-on-cash, meets-target flag)
and the max offer price. The CSV has one row per property for sorting in a spreadsheet.
````

- [ ] **Step 4: Commit**

```bash
git add plugins/rental/skills/report
git commit -m "feat(rental): add report skill (markdown + CSV)"
```

---

## Task 14: `setup` skill

**Files:**
- Create: `plugins/rental/skills/setup/SKILL.md`
- Create: `plugins/rental/skills/setup/scripts/setup.py`

**Interfaces:**
- Consumes: `config_path`, `merge_defaults`, `validate` (Task 4).
- Produces: CLI `setup.py --write` that reads a JSON object of user answers on stdin, merges defaults, validates, and writes to `config_path()`. Also `setup.py --show-path` prints the resolved path and whether it exists. The interactive Q&A is driven by Claude via the SKILL.md; the script just persists validated JSON.

- [ ] **Step 1: Write the script**

`plugins/rental/skills/setup/scripts/setup.py`:
```python
#!/usr/bin/env python3
"""Persist rental plugin config. Claude gathers answers (per SKILL.md) and pipes a
JSON object of user values to `--write`; this script merges defaults, validates, and
saves to the OS config dir. No secrets are echoed."""
import argparse
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.config import config_path, merge_defaults, validate


def main() -> int:
    ap = argparse.ArgumentParser(description="Write validated rental config")
    ap.add_argument("--write", action="store_true", help="Read user JSON on stdin and save")
    ap.add_argument("--show-path", action="store_true")
    args = ap.parse_args()

    path = config_path()
    if args.show_path:
        print(json.dumps({"path": str(path), "exists": path.is_file()}))
        return 0
    if args.write:
        user = json.load(sys.stdin)
        merged = merge_defaults(user)
        errors = validate(merged)
        if errors:
            print("error: " + "; ".join(errors), file=sys.stderr)
            return 2
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        print(f"wrote config to {path}", file=sys.stderr)
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify write + validation round-trip**

Run:
```bash
cd plugins/rental
export RENTAL_CONFIG=$(mktemp)
echo '{"market":{"label":"Springfield, IL","zips":["62701"]},"rentcast_api_key":"test"}' \
  | python skills/setup/scripts/setup.py --write
python skills/setup/scripts/setup.py --show-path
```
Expected: first command stderr `wrote config to ...`; second prints JSON with `"exists": true`. A missing `rentcast_api_key` should make `--write` exit 2 with an error listing the missing field.

- [ ] **Step 3: Write the SKILL.md**

`plugins/rental/skills/setup/SKILL.md`:
````markdown
---
name: setup
version: 0.1.0
description: One-time interactive setup for the rental plugin. Prompts for your market (city + ZIPs), RentCast API key, financing assumptions (down payment, term, closing costs, rate spread), expense defaults, deal thresholds, and screening rent heuristic, then writes them to your OS config dir (never the repo). Use the first time any rental skill runs and no config exists, or when the user asks to change their rental assumptions.
allowed-tools:
  - Bash
---

# setup

Writes the rental plugin's config to your OS config dir
(`%APPDATA%\personal-os\rental\config.json` on Windows,
`~/.config/personal-os/rental/config.json` otherwise). Never committed to the repo.

## When to run

- The first time a rental skill runs and `setup.py --show-path` reports `"exists": false`.
- Whenever the user wants to change assumptions.

## Procedure

1. Check the path/existence:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --show-path
   ```
2. Ask the user for (defaults come from `references/expense-defaults.json`, so only
   `market` and `rentcast_api_key` are strictly required — offer the documented defaults
   for the rest and let them adjust):
   - **Market**: city/label + list of ZIP codes to hunt in.
   - **RentCast API key**: free key from rentcast.io. Paste it; it is stored locally only.
   - **Financing**: down payment %, loan term, closing cost %, investment-rate spread,
     optional pinned rate.
   - **Expenses**: vacancy %, maintenance %, capex %, management %, insurance/yr,
     landlord-paid utilities/mo, property-tax fallback %.
   - **Thresholds**: target cash-on-cash %, min monthly cash flow, 1% rule on/off.
   - **Screening rent**: `per_sqft` (rent per sqft) or `per_bedroom` (rent by bedroom count).
3. Build a JSON object with the user's answers and pipe it to `--write`:
   ```bash
   echo '{"market":{"label":"...","zips":["..."]},"rentcast_api_key":"...", ...}' \
     | python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --write
   ```
4. Confirm the write succeeded. Do NOT print the API key back to the user.
````

- [ ] **Step 4: Commit**

```bash
git add plugins/rental/skills/setup
git commit -m "feat(rental): add setup skill for first-run config"
```

---

## Task 15: `analyze-rentals` orchestrator + final validation

**Files:**
- Create: `plugins/rental/skills/analyze-rentals/SKILL.md`

**Interfaces:**
- Consumes: all five skills above.
- Produces: end-to-end orchestration prose with the human gate. No new script.

- [ ] **Step 1: Write the orchestrator SKILL.md**

`plugins/rental/skills/analyze-rentals/SKILL.md`:
````markdown
---
name: analyze-rentals
version: 0.1.0
description: End-to-end rental analysis for 2-4 unit multifamily. Takes a Redfin CSV export, ingests and filters to 2-4 unit, screens with a zero-API heuristic, PAUSES for the user to prune the shortlist, then spends RentCast calls only on survivors and produces a ranked markdown + CSV report of cash-on-cash returns across price scenarios. Use when the user says "analyze these rentals", "run the rental pipeline", or hands over a Redfin CSV of multifamily listings.
allowed-tools:
  - Bash
  - Read
---

# analyze-rentals

Orchestrates the full pipeline. **The human review gate between screening and RentCast
enrichment is mandatory** — never spend API calls before the user prunes.

## Preconditions

Check config exists:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.py --show-path
```
If `"exists": false`, run `/setup` first (see setup SKILL.md), then continue.

## Pipeline

Use a temp working directory for intermediate JSON.

1. **Ingest** the Redfin CSV:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/ingest-listings/scripts/ingest.py "$CSV" > "$TMP/props.json"
   ```
2. **Screen** (zero API):
   ```bash
   cat "$TMP/props.json" | python3 ${CLAUDE_PLUGIN_ROOT}/skills/screen-deals/scripts/screen.py > "$TMP/screened.json"
   ```
3. **HUMAN GATE.** Present the ranked shortlist from `screened.json` (address, price,
   heuristic rent, asking cash-on-cash, max offer). Ask the user which to keep. Write the
   kept subset to `$TMP/pruned.json`. Do not proceed until they answer.
4. **Enrich** only the pruned set (metered — one RentCast call each):
   ```bash
   cat "$TMP/pruned.json" | python3 ${CLAUDE_PLUGIN_ROOT}/skills/enrich-rents/scripts/enrich.py > "$TMP/enriched.json"
   ```
   If it exits 4 (quota), tell the user how many were enriched and offer to continue with
   the partial set or resume next cycle.
5. **Report**:
   ```bash
   cat "$TMP/enriched.json" | python3 ${CLAUDE_PLUGIN_ROOT}/skills/report/scripts/report.py --out-dir .
   ```
6. Summarize the top results in chat and point the user to `rental-report.md` /
   `rental-report.csv`. Flag any property whose report notes mention thin/absent comps.

## Guardrails

- Never skip the human gate.
- Never print the RentCast API key.
- If ingest reports 0 kept rows, the Redfin search probably was not filtered to
  "Multi-family (2-4 Unit)" — tell the user to re-export.
````

- [ ] **Step 2: Full test suite + manifest validation**

Run: `cd plugins/rental && python -m pytest -v && cd ../.. && claude plugin validate plugins/rental && claude plugin validate .`
Expected: all unit tests pass; both validations report valid.

- [ ] **Step 3: Full pipeline smoke test (no live API)**

Run (drive ingest → screen → report directly, bypassing the metered enrich step with a hand-injected rent so no RentCast key is needed):
```bash
cd plugins/rental
export RENTAL_CONFIG=$(mktemp)
python3 -c "import json,lib.config as c; open('$RENTAL_CONFIG','w').write(json.dumps(c.merge_defaults({'market':{'label':'T','zips':['62701']},'rentcast_api_key':'k','screening':{'rent_per_sqft':2.5}})))"
python skills/ingest-listings/scripts/ingest.py tests/fixtures/redfin_sample.csv 2>/dev/null \
  | python skills/screen-deals/scripts/screen.py 2>/dev/null \
  | python skills/report/scripts/report.py --out-dir "$(mktemp -d)" >/dev/null && echo "PIPELINE OK"
```
Expected: prints `PIPELINE OK` with no traceback.

- [ ] **Step 4: Commit**

```bash
git add plugins/rental/skills/analyze-rentals
git commit -m "feat(rental): add analyze-rentals orchestrator with human gate"
```

---

## Task 16: Update root docs

**Files:**
- Modify: `CLAUDE.md` (root)

**Interfaces:** none (docs only).

- [ ] **Step 1: Document the new plugin in CLAUDE.md**

Add a short subsection under the marketplace description noting the second plugin. Insert after the `research` plugin description paragraph:
```markdown
The `rental` plugin (v0.1.0, 6 skills) analyzes local 2–4 unit multifamily listings for
long-term rental investment: it ingests a Redfin CSV export, screens with a zero-API rent
heuristic, pauses for human pruning, enriches the shortlist via RentCast, and reports
cash-on-cash returns across price scenarios. Shared logic lives in `plugins/rental/lib/`
(stdlib-only, unit-tested); skills are thin CLI wrappers. Config (with the RentCast key)
lives in the OS config dir, never the repo.
```

Also add to the "Common commands" area:
```markdown
# Rental plugin — run the test suite
cd plugins/rental && python -m pytest -v

# Rental pipeline (after /setup): ingest -> screen -> [prune] -> enrich -> report
python plugins/rental/skills/ingest-listings/scripts/ingest.py redfin.csv > props.json
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document rental plugin in CLAUDE.md"
```

---

## Self-Review

**1. Spec coverage:**
- Hybrid Redfin CSV + RentCast → Tasks 5, 8. ✓
- 2–4 unit only → Task 5 filter (`Multi-Family (2-4 Unit)`). ✓
- OS-config-dir config + first-run detection → Task 4 + every script's config guard + Task 14/15. ✓
- Itemized expenses w/ configurable defaults → Task 1 defaults + Task 3 engine. ✓
- Live rate + spread + fallback → Task 6. ✓
- Threshold pre-filter + rank + human gate → Tasks 7, 11, 15. ✓
- Capex excluded from NOI, reserve in cash flow, `--strict-cashflow` → Task 3 + Task 13 flag. ✓
- Scenario table + max-offer price → Task 3 `build_scenarios`/`max_offer_price`. ✓
- Markdown + CSV output → Task 9, 13. ✓
- Error handling (quota, rate fail, schema drift, missing tax) → Tasks 6, 8, 5, 3. ✓
- Tests on the pure core → Tasks 2–9 each ship tests. ✓
- Caching to `*.cache.json` gitignored → Task 1 `.gitignore` + Task 12. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; commands have expected output. One intentional note in Task 8 Step 3 instructs removing the temporary `# type: ignore` comments once the `from lib.models import Property` import is placed — this is a concrete instruction, not a placeholder.

**3. Type consistency:** `Property`, `Unit`, `Scenario`, `DealResult` and their `to_dict`/`from_dict` are defined in Task 2 and used with identical field names throughout. `compute_returns` returns the same 5 keys everywhere it is consumed (Tasks 7, 13). `effective_rate` returns `(rate, note)` in Tasks 6, 11, 13. `enrich_property(prop, api_key, cache, fetcher=...)` signature matches between Task 8 and Task 12.

**Fixes applied inline:** Task 8's implementation note about the `Property` import was clarified so the engineer does not ship dangling `# type: ignore` comments or a forward-referenced type.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-11-rental-plugin.md`.
