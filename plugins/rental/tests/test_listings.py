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


def test_url_column_with_redfin_pricing_disclaimer_suffix():
    # Real Redfin "Download All" exports name this column
    # 'URL (SEE https://.../comparative-market-analysis FOR INFO ON PRICING)',
    # not a plain 'URL' -- confirmed against a real 2026-07 export. The column
    # must be matched by prefix, not exact name, or every property's url silently
    # comes back empty.
    text = (
        "PROPERTY TYPE,ADDRESS,CITY,STATE OR PROVINCE,ZIP OR POSTAL CODE,PRICE,"
        "URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis "
        "FOR INFO ON PRICING)\n"
        "Multi-Family (2-4 Unit),1 A St,Springfield,IL,62701,250000,"
        "https://www.redfin.com/IL/Springfield/1-A-St/home/1\n"
    )
    props, _ = parse_redfin_csv(text)
    assert props[0].url == "https://www.redfin.com/IL/Springfield/1-A-St/home/1"
