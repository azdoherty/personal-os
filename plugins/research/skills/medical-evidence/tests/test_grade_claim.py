import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from grade_claim import evidence_grade, cost_tier, risk_cost_grade


def test_meta_analysis_clinical_direct_is_high():
    assert evidence_grade("clinical-outcome", "meta-analysis", "direct", "consistent", 5) == 5


def test_mechanism_only_capped_at_2_even_with_meta_analysis():
    # Regression invariant: mechanism evidence can never read as strong.
    assert evidence_grade("mechanism-only", "meta-analysis", "direct", "consistent", 9) == 2


def test_distant_population_downgrades():
    assert evidence_grade("clinical-outcome", "rct", "distant", "consistent", 3) == 3


def test_contradicted_floors_to_1():
    assert evidence_grade("clinical-outcome", "rct", "direct", "contradicted", 4) == 1


def test_no_studies_floors_to_1():
    assert evidence_grade("clinical-outcome", "none", "none", "consistent", 0) == 1


def test_cost_tiers():
    assert cost_tier(12) == "low"
    assert cost_tier(30) == "moderate"
    assert cost_tier(90) == "high"


def test_low_risk_cheap_is_max():
    assert risk_cost_grade("low", 10, "immediate") == 5


def test_high_cost_pulls_grade_down():
    assert risk_cost_grade("low", 90, "immediate") == 3


def test_permanent_reversibility_caps_at_2():
    assert risk_cost_grade("low", 10, "permanent") == 2


def test_high_risk_bottoms_out():
    assert risk_cost_grade("high", 90, "immediate") == 1
