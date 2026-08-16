import os, sys, json, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from grade_claim import evidence_grade, cost_tier, risk_cost_grade, classify, hype_risk, required_hedge, grade

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "grade_claim.py")


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


def test_collagen_is_well_supported():
    assert classify(4, 5, "clinical-outcome", "direct", "consistent", None, 20, "low") == "well-supported"


def test_citrulline_is_worth_trying_anyway():
    # weak evidence, plausible mechanism, cheap, safe, structurally understudied
    assert classify(2, 5, "mechanism-only", "distant", "mixed",
                    "untested-low-commercial-incentive", 12, "low") == "worth-trying-anyway"


def test_moringa_for_tendon_is_marketing_claim():
    assert classify(1, 5, "mechanism-only", "none", "mixed",
                    "untested-implausible", 10, "low") == "marketing-claim"


def test_urolithin_a_is_unproven_and_costly():
    assert classify(2, 3, "clinical-outcome", "distant", "mixed",
                    "too-new", 80, "low") == "unproven-and-costly"


def test_bpc157_is_avoid():
    assert classify(2, 1, "mechanism-only", "none", "mixed",
                    "too-new", 60, "high") == "avoid"


def test_refuted_is_avoid():
    assert classify(1, 5, "clinical-outcome", "direct", "contradicted", None, 10, "low") == "avoid"


def test_hype_risk_true_when_popular_but_no_evidence():
    assert hype_risk("high", 2) is True
    assert hype_risk("low", 2) is False


def test_hedge_exists_for_every_quadrant():
    for q in ("well-supported", "worth-trying-anyway", "unproven-and-costly",
              "marketing-claim", "avoid"):
        assert required_hedge(q)


def test_grade_produces_full_record():
    claim = {
        "claim": "L-citrulline improves tendon healing in adults with tendinosis",
        "outcome_type": "mechanism-only", "best_study_tier": "in-vitro",
        "population_match": "none", "consistency": "mixed", "n_studies": 0,
        "absence_reason": "untested-low-commercial-incentive",
        "risk": "low", "cost_per_month": 12, "reversibility": "immediate",
        "community_frequency": "moderate",
    }
    out = grade(claim)
    assert out["verdict_quadrant"] == "worth-trying-anyway"
    assert out["evidence_grade"] == 1
    assert out["required_hedge"]
    assert out["what_would_change_this"]


def test_main_sorts_list_by_priority(tmp_path):
    claims = [
        {"claim": "weak", "outcome_type": "mechanism-only", "best_study_tier": "in-vitro",
         "population_match": "none", "consistency": "mixed", "n_studies": 0,
         "absence_reason": "too-new", "risk": "high", "cost_per_month": 90,
         "reversibility": "immediate", "community_frequency": "none"},
        {"claim": "strong", "outcome_type": "clinical-outcome", "best_study_tier": "meta-analysis",
         "population_match": "direct", "consistency": "consistent", "n_studies": 5,
         "absence_reason": None, "risk": "low", "cost_per_month": 10,
         "reversibility": "immediate", "community_frequency": "none"},
    ]
    res = subprocess.run([sys.executable, SCRIPT], input=json.dumps(claims),
                         capture_output=True, text=True)
    assert res.returncode == 0
    parsed = json.loads(res.stdout)
    assert parsed[0]["claim"] == "strong"   # highest priority first
