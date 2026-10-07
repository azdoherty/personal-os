import json
import pathlib

import pytest

from lib.sources.html_table import parse_tables
from lib.sources.manual import parse_manual
from lib.sources.newenglandoil import fetch_zone, state_for_zip, zone_url

FIX = pathlib.Path(__file__).parent / "fixtures"


def _read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_zone_listing_parses_dealers_prices_and_phone_under_name():
    qs = parse_tables(_read("zone_listing.html"), "nlo", base_url="https://x.test/nh/zone10.asp")
    by = {q.dealer: q for q in qs}
    assert set(by) == {"Seacoast Fuel Co", "Granite Discount Oil, LLC", "Old Price Oil"}
    s = by["Seacoast Fuel Co"]
    assert s.tiers == {100: 3.399}
    assert s.phone == "(603) 555-0101"
    assert s.town == "Portsmouth"
    assert s.updated == "2026-10-06"
    assert s.url == "https://x.test/dealer.asp?id=11"


def test_row_without_price_is_skipped():
    qs = parse_tables(_read("zone_listing.html"), "nlo")
    assert "Call For Price Inc" not in {q.dealer for q in qs}


def test_tiered_columns_become_volume_tiers():
    qs = parse_tables(_read("tiered_listing.html"), "ex")
    b = next(q for q in qs if q.dealer == "Blue Flame Energy")
    assert b.tiers == {100: 3.50, 150: 3.31}
    assert b.phone == "603.555.0199"
    assert b.updated == "2026-10-05"


def test_no_matching_table_yields_nothing():
    assert parse_tables("<table><tr><td>a</td><td>b</td></tr></table>", "x") == []


def test_state_for_zip():
    assert state_for_zip("03801") == "NH"
    assert state_for_zip("02139") == "MA"
    assert state_for_zip("06101") == "CT"
    assert state_for_zip("10001") is None


def test_zone_url_and_fetch_with_injected_fetcher():
    assert zone_url("NH", 10) == "https://www.newenglandoil.com/newhampshire/zone10.asp?x=0"
    qs = fetch_zone("NH", 10, fetch=lambda url: _read("zone_listing.html"))
    assert qs and all(q.sources == ["newenglandoil:NH-zone10"] for q in qs)


def test_manual_quotes_accept_price_or_tiers():
    qs = parse_manual(json.loads(_read("quotes.json")))
    assert qs[0].tiers == {100: 3.399}
    assert qs[1].tiers == {100: 3.50, 150: 3.31}
    assert qs[2].sources == ["manual"]


def test_manual_quote_without_price_errors():
    with pytest.raises(ValueError):
        parse_manual([{"dealer": "X"}])
