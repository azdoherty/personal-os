from datetime import date

from lib.models import Quote
from lib.reputation import (bbb_score, google_score, integrity_score,
                            score_dealer, years_score)

TODAY = date(2026, 10, 7)


def _q(**kw):
    return Quote(**{"dealer": "X", "tiers": {100: 3.0}, "updated": "2026-10-06",
                    "sources": ["a"], **kw})


def test_missing_signals_are_neutral_and_inconclusive():
    r = score_dealer(_q(), None, today=TODAY)
    assert r["verdict"] == "inconclusive"
    assert r["researched"] is False


def test_strong_dealer_is_reputable():
    sig = {"google_rating": 4.8, "google_reviews": 400, "bbb_grade": "A+",
           "bbb_accredited": True, "years_in_business": 30, "complaint_hits": 0}
    r = score_dealer(_q(sources=["a", "b"]), sig, today=TODAY)
    assert r["score"] >= 90 and r["verdict"] == "reputable"


def test_bad_dealer_is_avoid():
    sig = {"google_rating": 2.0, "google_reviews": 80, "bbb_grade": "F",
           "years_in_business": 1, "complaint_hits": 3}
    assert score_dealer(_q(), sig, today=TODAY)["verdict"] == "avoid"


def test_few_reviews_pull_toward_neutral():
    assert google_score(5.0, 2) < google_score(5.0, 300)
    assert google_score(1.0, 2) > google_score(1.0, 300)
    assert google_score(None, None) == 50


def test_component_scores():
    assert bbb_score("A+", True, {"A+": 100}) == 100
    assert bbb_score(None, None, {}) == 50
    assert years_score(20) == 100 and years_score(None) == 50
    assert integrity_score(0) == 100 and integrity_score(3) == 0


def test_stale_price_lowers_score():
    fresh = score_dealer(_q(), {}, today=TODAY)["score"]
    stale = score_dealer(_q(updated="2026-08-01"), {}, today=TODAY)["score"]
    assert stale < fresh
