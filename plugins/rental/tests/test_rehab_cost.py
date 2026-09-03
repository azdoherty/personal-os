import pytest
from lib.rehab_cost import estimate_project, UnknownProjectTypeError, TierError, total_rehab_cost, render_markdown

TEST_REFERENCE = {
    "bathroom_remodel": {
        "tiers": ["economy", "luxury"],
        "line_items": [
            {"name": "Tile - floor", "unit": "sqft",
             "parts": {"economy": 3.0, "luxury": 10.0},
             "labor": {"economy": 7.0, "luxury": 12.0}},
            {"name": "Toilet", "unit": "each",
             "parts": {"economy": 150.0, "luxury": 700.0},
             "labor": {"economy": 150.0, "luxury": 250.0}},
        ],
    },
    "roof_replacement": {
        "tiers": None,
        "line_items": [
            {"name": "Tear-off, underlayment, shingle, flashing", "unit": "sqft",
             "parts": 2.5, "labor": 4.5},
        ],
    },
    "electrical": {
        "tiers": None,
        "line_items": [
            {"name": "General rewire", "unit": "sqft", "parts": 3.0, "labor": 5.0},
            {"name": "Knob-and-tube removal", "unit": "sqft", "parts": 4.0, "labor": 8.0,
             "trigger": "year_built < 1960"},
        ],
    },
}


def test_sqft_line_item_computed_correctly_single_tier():
    est = estimate_project("roof_replacement", sqft=1450, reference=TEST_REFERENCE)
    assert est.parts_total == pytest.approx(1450 * 2.5)
    assert est.labor_total == pytest.approx(1450 * 4.5)
    assert est.total == pytest.approx(1450 * 7.0)
    assert len(est.line_items) == 1
    assert est.line_items[0].quantity == 1450


def test_each_line_item_with_fixture_count_override():
    est = estimate_project("bathroom_remodel", sqft=50, tier="economy",
                           fixture_counts={"Toilet": 2}, reference=TEST_REFERENCE)
    toilet = next(li for li in est.line_items if li.name == "Toilet")
    assert toilet.quantity == 2
    assert toilet.subtotal == pytest.approx(2 * (150.0 + 150.0))


def test_each_line_item_defaults_to_one_fixture():
    est = estimate_project("bathroom_remodel", sqft=50, tier="luxury",
                           reference=TEST_REFERENCE)
    toilet = next(li for li in est.line_items if li.name == "Toilet")
    assert toilet.quantity == 1
    assert toilet.subtotal == pytest.approx(700.0 + 250.0)


def test_knob_and_tube_included_for_pre_1960_property():
    est = estimate_project("electrical", sqft=2000, year_built=1902,
                           reference=TEST_REFERENCE)
    names = [li.name for li in est.line_items]
    assert "Knob-and-tube removal" in names
    kt = next(li for li in est.line_items if li.name == "Knob-and-tube removal")
    assert kt.subtotal == pytest.approx(2000 * (4.0 + 8.0))
    assert est.warnings == []


def test_knob_and_tube_excluded_for_post_1960_property():
    est = estimate_project("electrical", sqft=2000, year_built=1975,
                           reference=TEST_REFERENCE)
    names = [li.name for li in est.line_items]
    assert "Knob-and-tube removal" not in names
    assert est.warnings == []


def test_knob_and_tube_excluded_with_warning_when_year_built_unknown():
    est = estimate_project("electrical", sqft=2000, year_built=None,
                           reference=TEST_REFERENCE)
    names = [li.name for li in est.line_items]
    assert "Knob-and-tube removal" not in names
    assert len(est.warnings) == 1
    assert "year_built unknown" in est.warnings[0]


def test_unknown_project_type_raises_with_valid_types_listed():
    with pytest.raises(UnknownProjectTypeError) as e:
        estimate_project("swimming_pool", sqft=100, reference=TEST_REFERENCE)
    assert "bathroom_remodel" in str(e.value)


def test_tier_required_but_missing_raises():
    with pytest.raises(TierError):
        estimate_project("bathroom_remodel", sqft=50, reference=TEST_REFERENCE)


def test_tier_supplied_but_not_allowed_raises():
    with pytest.raises(TierError):
        estimate_project("roof_replacement", sqft=1450, tier="economy",
                         reference=TEST_REFERENCE)


def test_total_rehab_cost_sums_multiple_projects():
    roof = estimate_project("roof_replacement", sqft=1450, reference=TEST_REFERENCE)
    bath = estimate_project("bathroom_remodel", sqft=50, tier="economy",
                            reference=TEST_REFERENCE)
    result = total_rehab_cost([roof, bath])
    assert result.grand_total == pytest.approx(roof.total + bath.total)
    assert len(result.projects) == 2


def test_total_rehab_cost_empty_list():
    result = total_rehab_cost([])
    assert result.grand_total == 0.0
    assert result.projects == []


def test_render_markdown_includes_line_items_and_grand_total():
    roof = estimate_project("roof_replacement", sqft=1450, reference=TEST_REFERENCE)
    result = total_rehab_cost([roof])
    md = render_markdown(result)
    assert "Roof Replacement" in md
    assert "Tear-off, underlayment, shingle, flashing" in md
    assert f"${roof.total:,.2f}" in md
    assert f"${result.grand_total:,.2f}" in md


def test_render_markdown_surfaces_warnings():
    est = estimate_project("electrical", sqft=2000, year_built=None, reference=TEST_REFERENCE)
    result = total_rehab_cost([est])
    md = render_markdown(result)
    assert "year_built unknown" in md
