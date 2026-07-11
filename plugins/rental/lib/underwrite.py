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
