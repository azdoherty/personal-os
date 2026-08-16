"""Grade a single health claim on independent axes. Stdlib only."""
import json
import sys

_TIER = {
    "meta-analysis": 5, "systematic-review": 5, "rct": 4, "cohort": 3,
    "case-series": 2, "animal": 2, "in-vitro": 1, "none": 1,
}


def evidence_grade(outcome_type, best_study_tier, population_match, consistency, n_studies):
    base = _TIER[best_study_tier]
    if outcome_type == "mechanism-only":
        base = min(base, 2)
    elif outcome_type == "surrogate":
        base = min(base, 3)
    if population_match == "none":
        base = min(base, 2)
    elif population_match == "distant":
        base = max(1, base - 1)
    if consistency == "mixed":
        base = max(1, base - 1)
    elif consistency == "contradicted":
        base = 1
    if n_studies <= 0:
        base = min(base, 1)
    return max(1, min(5, base))


_RISK = {"low": 3, "moderate": 1, "high": 0}
_COST = {"low": 2, "moderate": 1, "high": 0}


def cost_tier(cost_per_month):
    if cost_per_month <= 15:
        return "low"
    if cost_per_month <= 50:
        return "moderate"
    return "high"


def risk_cost_grade(risk, cost_per_month, reversibility):
    score = _RISK[risk] + _COST[cost_tier(cost_per_month)]
    grade = max(1, min(5, score))
    if reversibility == "permanent":
        grade = min(grade, 2)
    return grade


def classify(ev, rc, outcome_type, population_match, consistency, absence_reason, cost_per_month, risk):
    if consistency == "contradicted":
        return "avoid"                       # tested and refuted
    if risk == "high":
        return "avoid"                       # risk dominates any plausible benefit
    if ev >= 4 and outcome_type == "clinical-outcome" and population_match in ("direct", "adjacent"):
        return "well-supported"
    if absence_reason == "untested-implausible":
        return "marketing-claim"             # promoted, no mechanism for THIS claim
    if cost_tier(cost_per_month) == "high":
        return "unproven-and-costly"
    if absence_reason == "untested-low-commercial-incentive" and rc >= 4:
        return "worth-trying-anyway"         # cheap, safe, structurally understudied
    return "worth-trying-anyway" if rc >= 4 else "unproven-and-costly"
