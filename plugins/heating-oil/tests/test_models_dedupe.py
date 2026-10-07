from datetime import date

from lib.dedupe import merge_quotes, source_count
from lib.models import Quote, dealer_key, normalize_name, parse_date, parse_price


def test_parse_price():
    assert parse_price("$3.399") == 3.399
    assert parse_price("3.45/gal") == 3.45
    assert parse_price("call") is None
    assert parse_price("$123.45") is None


def test_parse_date_formats():
    assert parse_date("10/06/26") == "2026-10-06"
    assert parse_date("2026-10-06") == "2026-10-06"
    assert parse_date("Oct 6, 2026") == "2026-10-06"
    assert parse_date("10/06", today=date(2026, 10, 7)) == "2026-10-06"
    assert parse_date("12/30", today=date(2026, 1, 2)) == "2025-12-30"
    assert parse_date("yesterday") is None


def test_dealer_key_prefers_phone():
    assert dealer_key("Seacoast Fuel Co", "1-603-555-0101") == "6035550101"
    assert dealer_key("Seacoast Fuel, Inc.") == "seacoast fuel"
    assert normalize_name("Smith & Sons Oil LLC") == "smith and sons oil"


def test_merge_by_phone_keeps_lowest_tier_prices_and_unions_sources():
    a = Quote("Seacoast Fuel Co", {100: 3.399}, phone="(603) 555-0101",
              updated="2026-10-06", sources=["newenglandoil:NH-zone10"])
    b = Quote("Seacoast Fuel Company", {100: 3.45, 150: 3.35}, phone="603-555-0101",
              updated="2026-10-05", sources=["example.com"], town="Portsmouth")
    c = Quote("Seacoast Fuel Co", {100: 3.41}, sources=["newenglandoil:NH-zone11"])
    [m] = merge_quotes([a, b, c])
    assert m.tiers == {100: 3.399, 150: 3.35}
    assert m.updated == "2026-10-06"
    assert m.town == "Portsmouth"
    assert source_count(m) == 2       # two zones of one site count once


def test_distinct_dealers_stay_separate():
    qs = merge_quotes([Quote("A Oil", {100: 3.0}), Quote("B Oil", {100: 3.1})])
    assert len(qs) == 2
