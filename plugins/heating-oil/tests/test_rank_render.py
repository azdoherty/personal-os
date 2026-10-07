from datetime import date

from lib.rank import rank, tier_price
from lib.render import render_markdown

TODAY = date(2026, 10, 7)


def _e(dealer, tiers, score, **kw):
    return {"dealer": dealer, "tiers": tiers, "updated": "2026-10-06",
            "reputation": {"score": score, "verdict": "reputable" if score >= 70 else "avoid",
                           "researched": True}, "sources": ["s"], **kw}


def test_tier_price_picks_largest_qualifying_tier():
    assert tier_price({"100": 3.5, "150": 3.3}, 150) == (150, 3.3)
    assert tier_price({"100": 3.5, "150": 3.3}, 120) == (100, 3.5)
    assert tier_price({"150": 3.3}, 100) is None


def test_rank_orders_by_total_and_excludes_with_reasons():
    entries = [
        _e("Good", {"100": 3.40}, 90),
        _e("Tiered", {"100": 3.50, "150": 3.30}, 80, fee=5),
        _e("Shady", {"100": 2.90}, 20),
        _e("Stale", {"100": 2.95}, 90, updated="2026-09-01"),
        _e("BigMin", {"100": 3.00}, 90, min_delivery_gallons=200),
        _e("Blocked", {"100": 2.80}, 95),
        _e("Friend", {"100": 3.45}, 30),
    ]
    r = rank(entries, gallons=150, min_score=70, max_age_days=7,
             allowlist=["Friend"], blocklist=["blocked"], today=TODAY)
    assert [e["dealer"] for e in r["ranked"]] == ["Tiered", "Good", "Friend"]
    assert r["ranked"][0]["total"] == round(3.30 * 150 + 5, 2)
    reasons = {e["dealer"]: e["excluded_reason"] for e in r["excluded"]}
    assert "reputation" in reasons["Shady"]
    assert "days old" in reasons["Stale"]
    assert "minimum delivery" in reasons["BigMin"]
    assert "blocklist" in reasons["Blocked"]


def test_render_markdown_has_best_line_table_and_excluded():
    r = rank([_e("Good", {"100": 3.40}, 90, phone="603-555-0101"), _e("Shady", {"100": 2.9}, 20)],
             gallons=150, min_score=70, max_age_days=7, today=TODAY)
    md = render_markdown(r, 150, "03801", benchmark=3.60)
    assert "**Best: Good**" in md and "603-555-0101" in md
    assert "$0.200/gal below the benchmark" in md
    assert "| 1 | Good |" in md
    assert "Shady" in md and "reputation 20" in md


def test_render_when_nothing_passes():
    r = rank([_e("Shady", {"100": 2.9}, 20)], 150, 70, 7, today=TODAY)
    assert "No dealer passed" in render_markdown(r, 150)


def test_render_warns_when_best_is_not_reputable():
    r = rank([_e("Meh", {"100": 3.0}, 55)], 150, 40, 7, today=TODAY)
    md = render_markdown(r, 150)
    assert "**Best: Meh**" in md and "Reputation is **avoid**" in md
    good = render_markdown(rank([_e("Good", {"100": 3.0}, 90)], 150, 70, 7, today=TODAY), 150)
    assert "⚠️" not in good
