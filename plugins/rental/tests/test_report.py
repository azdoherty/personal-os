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
