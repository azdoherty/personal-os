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
