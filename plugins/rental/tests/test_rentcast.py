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
