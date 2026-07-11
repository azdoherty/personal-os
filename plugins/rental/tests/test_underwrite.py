import pytest
from lib.models import Property
from lib.underwrite import (
    monthly_payment, compute_returns, max_offer_price, build_scenarios,
    UnboundedReturnError,
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


def test_max_offer_price_raises_when_cash_on_cash_improves_without_bound():
    # Same "cost exceeds income at any price" property as the unachievable test, but
    # with a NEGATIVE target (an edge case, not a realistic config value, but the only
    # way to make cash_on_cash's increasing-but-negative trajectory actually clear a
    # target). Old code's first guard (coc(lo) < target -> None) would have wrongly
    # reported this as unreachable; it IS reachable at high-enough prices, just with
    # no finite maximum (every higher price also clears it). The hardened version must
    # distinguish "unreachable" from "reachable without a finite bound" instead of
    # conflating both under None.
    p = Property(address="W", list_price=500000.0, gross_monthly_rent=100.0)
    with pytest.raises(UnboundedReturnError):
        max_offer_price(p, ASSUMPTIONS, effective_rate=0.075, target_coc=-0.5)


def test_build_scenarios_labels_and_flags():
    p = Property(address="X", list_price=200000.0, gross_monthly_rent=3500.0)
    scenarios, max_price = build_scenarios(p, ASSUMPTIONS, effective_rate=0.075)
    assert [s.label for s in scenarios] == ["asking", "-5%", "-10%"]
    assert scenarios[0].price == pytest.approx(200000.0)
    assert scenarios[1].price == pytest.approx(190000.0)
    # meets_target is True only where CoC >= target.
    for s in scenarios:
        assert s.meets_target == (s.cash_on_cash >= 0.08 - 1e-9)
