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
