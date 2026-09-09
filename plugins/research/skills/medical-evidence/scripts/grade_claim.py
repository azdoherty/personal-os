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


_HEDGE = {
    "well-supported": "Supported by human outcome evidence in a matching population.",
    "worth-trying-anyway": "Plausible mechanism and low risk/cost, but NOT proven for this "
                           "outcome. Frame as a cheap bet, never a treatment to rely on.",
    "unproven-and-costly": "Weak evidence and real expense — fund this only after the "
                           "well-supported items.",
    "marketing-claim": "No human evidence and no mechanism for this specific claim; treat as "
                       "marketing until a study exists.",
    "avoid": "Either refuted, or the risk/irreversibility outweighs any plausible benefit.",
}


def hype_risk(community_frequency, ev):
    return community_frequency == "high" and ev <= 2


def required_hedge(quadrant):
    return _HEDGE[quadrant]


def what_would_change_this(outcome_type, population_match, absence_reason):
    if absence_reason == "tested-and-refuted":
        return "A well-powered replication reversing the negative finding."
    if outcome_type in ("mechanism-only", "surrogate"):
        return ("A human RCT measuring the actual clinical outcome (not the mechanism or a "
                "surrogate marker) in a matching population.")
    if population_match in ("distant", "none"):
        return "A trial in a population like the user's, rather than extrapolated from another group."
    return "Larger or more consistent human trials replicating the effect."


def grade(claim):
    ev = evidence_grade(claim["outcome_type"], claim["best_study_tier"],
                        claim["population_match"], claim["consistency"], claim.get("n_studies", 0))
    rc = risk_cost_grade(claim["risk"], claim["cost_per_month"], claim["reversibility"])
    quadrant = classify(ev, rc, claim["outcome_type"], claim["population_match"],
                        claim["consistency"], claim.get("absence_reason"),
                        claim["cost_per_month"], claim["risk"])
    freq = claim.get("community_frequency", "none")
    return {
        "claim": claim["claim"],
        "evidence_grade": ev,
        "risk_cost_grade": rc,
        "community_frequency": freq,
        "verdict_quadrant": quadrant,
        "hype_risk": hype_risk(freq, ev),
        "absence_reason": claim.get("absence_reason"),
        "priority_score": ev + rc,
        "required_hedge": required_hedge(quadrant),
        "what_would_change_this": what_would_change_this(
            claim["outcome_type"], claim["population_match"], claim.get("absence_reason")),
    }


_QUADRANT_RANK = {
    "well-supported": 0,
    "worth-trying-anyway": 1,
    "unproven-and-costly": 2,
    "marketing-claim": 3,
    "avoid": 4,
}


def main():
    raw = sys.stdin.buffer.read().decode("utf-8")
    data = json.loads(raw)
    claims = data if isinstance(data, list) else [data]
    graded = [grade(c) for c in claims]
    graded.sort(key=lambda g: (_QUADRANT_RANK[g["verdict_quadrant"]], -g["priority_score"]))
    out = graded if isinstance(data, list) else graded[0]
    print(json.dumps(out, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
