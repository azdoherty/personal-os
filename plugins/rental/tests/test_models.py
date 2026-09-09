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
