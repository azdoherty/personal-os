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
