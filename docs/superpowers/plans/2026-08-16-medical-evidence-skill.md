# medical-evidence Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `medical-evidence` skill to the `research` plugin that enumerates the full solution space for a health problem, then grades each candidate on three independent axes with a reproducible scoring script.

**Architecture:** House pattern — a stdlib-only `grade_claim.py` computes deterministic grades from structured claim JSON; `SKILL.md` orchestrates the enumerate → grade → interaction-check → rank → rollout pipeline. Wired into `literature-review` for medical intent and invocable standalone.

**Tech Stack:** Python 3 (stdlib only), pytest for tests, Markdown SKILL.md.

## Global Constraints

- **Stdlib-only Python. No pip dependencies.** (Repo rule, `CLAUDE.md`.)
- **JSON output uses `ensure_ascii=True`.** (Repo convention, commit c1b91ae — avoids Windows cp1252 console crashes on non-ASCII study text.)
- **Scripts compute scores; skills orchestrate.** Grading logic lives only in `grade_claim.py`; no scoring judgment in SKILL.md prose.
- **A `mechanism-only` claim can never produce a `well-supported` verdict.** Regression invariant, enforced by test.
- **Plugin version is authoritative in `plugin.json`.** Bump `research` 0.5.0 → 0.6.0.
- Run tests from repo root: `python -m pytest plugins/research/skills/medical-evidence/tests/ -v`

## File Structure

- Create: `plugins/research/skills/medical-evidence/scripts/grade_claim.py` — grading engine (pure functions + thin `main()`).
- Create: `plugins/research/skills/medical-evidence/tests/test_grade_claim.py` — unit tests + session fixtures.
- Create: `plugins/research/skills/medical-evidence/SKILL.md` — pipeline orchestration.
- Modify: `plugins/research/skills/literature-review/SKILL.md` — insert Step 3.5 hand-off.
- Modify: `plugins/research/.claude-plugin/plugin.json` — version + description.
- Modify: `.claude-plugin/marketplace.json` — research description.
- Modify: `CLAUDE.md` — document the new skill.

---

### Task 1: Scaffold skill + `evidence_grade()`

**Files:**
- Create: `plugins/research/skills/medical-evidence/scripts/grade_claim.py`
- Test: `plugins/research/skills/medical-evidence/tests/test_grade_claim.py`

**Interfaces:**
- Produces: `evidence_grade(outcome_type: str, best_study_tier: str, population_match: str, consistency: str, n_studies: int) -> int` (returns 1–5).

- [ ] **Step 1: Write the failing tests**

```python
# plugins/research/skills/medical-evidence/tests/test_grade_claim.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from grade_claim import evidence_grade


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/test_grade_claim.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'grade_claim'`

- [ ] **Step 3: Write minimal implementation**

```python
# plugins/research/skills/medical-evidence/scripts/grade_claim.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/test_grade_claim.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add plugins/research/skills/medical-evidence/scripts/grade_claim.py plugins/research/skills/medical-evidence/tests/test_grade_claim.py
git commit -m "feat(research): evidence_grade for medical-evidence skill"
```

---

### Task 2: `cost_tier()` + `risk_cost_grade()`

**Files:**
- Modify: `plugins/research/skills/medical-evidence/scripts/grade_claim.py`
- Test: `plugins/research/skills/medical-evidence/tests/test_grade_claim.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `cost_tier(cost_per_month: float) -> str` (`"low"`|`"moderate"`|`"high"`); `risk_cost_grade(risk: str, cost_per_month: float, reversibility: str) -> int` (1–5, **5 = safest and cheapest**).

- [ ] **Step 1: Write the failing tests**

```python
# append to test_grade_claim.py
from grade_claim import cost_tier, risk_cost_grade


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/test_grade_claim.py -v`
Expected: FAIL — `ImportError: cannot import name 'cost_tier'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to grade_claim.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/test_grade_claim.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add plugins/research/skills/medical-evidence/scripts/grade_claim.py plugins/research/skills/medical-evidence/tests/test_grade_claim.py
git commit -m "feat(research): risk_cost_grade + cost_tier"
```

---

### Task 3: `classify()` verdict quadrants

**Files:**
- Modify: `plugins/research/skills/medical-evidence/scripts/grade_claim.py`
- Test: `plugins/research/skills/medical-evidence/tests/test_grade_claim.py`

**Interfaces:**
- Consumes: `cost_tier` (Task 2).
- Produces: `classify(ev: int, rc: int, outcome_type: str, population_match: str, consistency: str, absence_reason, cost_per_month: float, risk: str) -> str` returning one of `well-supported | worth-trying-anyway | unproven-and-costly | marketing-claim | avoid`.

- [ ] **Step 1: Write the failing tests** (these are the session fixtures)

```python
# append to test_grade_claim.py
from grade_claim import classify


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/test_grade_claim.py -v`
Expected: FAIL — `ImportError: cannot import name 'classify'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to grade_claim.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/test_grade_claim.py -v`
Expected: PASS (16 passed)

- [ ] **Step 5: Commit**

```bash
git add plugins/research/skills/medical-evidence/scripts/grade_claim.py plugins/research/skills/medical-evidence/tests/test_grade_claim.py
git commit -m "feat(research): verdict quadrant classifier"
```

---

### Task 4: Output assembly — `grade()` + `main()` JSON I/O

**Files:**
- Modify: `plugins/research/skills/medical-evidence/scripts/grade_claim.py`
- Test: `plugins/research/skills/medical-evidence/tests/test_grade_claim.py`

**Interfaces:**
- Consumes: all of `evidence_grade`, `risk_cost_grade`, `classify` (Tasks 1–3).
- Produces: `hype_risk(community_frequency: str, ev: int) -> bool`; `required_hedge(quadrant: str) -> str`; `what_would_change_this(outcome_type: str, population_match: str, absence_reason) -> str`; `grade(claim: dict) -> dict` (keys: `claim, evidence_grade, risk_cost_grade, community_frequency, verdict_quadrant, hype_risk, absence_reason, priority_score, required_hedge, what_would_change_this`); `main()` reads one claim or a list from stdin, writes graded JSON to stdout (a list is sorted by `priority_score` descending).

- [ ] **Step 1: Write the failing tests**

```python
# append to test_grade_claim.py
import json, subprocess
from grade_claim import hype_risk, required_hedge, grade

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "grade_claim.py")


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/test_grade_claim.py -v`
Expected: FAIL — `ImportError: cannot import name 'hype_risk'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to grade_claim.py
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


def main():
    data = json.load(sys.stdin)
    claims = data if isinstance(data, list) else [data]
    graded = [grade(c) for c in claims]
    graded.sort(key=lambda g: g["priority_score"], reverse=True)
    out = graded if isinstance(data, list) else graded[0]
    print(json.dumps(out, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/test_grade_claim.py -v`
Expected: PASS (20 passed)

- [ ] **Step 5: Commit**

```bash
git add plugins/research/skills/medical-evidence/scripts/grade_claim.py plugins/research/skills/medical-evidence/tests/test_grade_claim.py
git commit -m "feat(research): grade() aggregator + stdin/stdout main"
```

---

### Task 5: Author `SKILL.md`

**Files:**
- Create: `plugins/research/skills/medical-evidence/SKILL.md`

**Interfaces:**
- Consumes: `scripts/grade_claim.py` (invoked as a subprocess with claim JSON on stdin).
- Produces: the documented pipeline other skills and Claude follow.

- [ ] **Step 1: Write SKILL.md**

Write the file with this exact content:

````markdown
---
name: medical-evidence
description: Rigor layer for health/medical questions. Use whenever a question involves a treatment, supplement, procedure, or intervention for a health condition — before recommending anything. Enumerates the full solution space (not just the options the user named), grades each candidate on evidence strength, risk/cost, and community frequency, and separates "untested because unpatentable" from "tested and refuted." Produces a ranked, deployable shortlist with required hedges and a clinician hand-off.
---

# medical-evidence

Turn a health problem into a ranked, honestly-graded shortlist of interventions. Invoked as
a mandatory step by `literature-review` for `medical` intent, and standalone for any health
question that does not warrant a full review.

## Why this exists

Confirmatory questions ("does X help?") only validate a candidate someone already named, and
a single evidence score hides whether "no trials" means *refuted* or *never funded*. This
skill enumerates first, then grades on independent axes.

## Pipeline

### 0. Enumerate the solution space (before evaluating anything)

Search the **problem**, not the solution. Run enumerative queries across four lanes:

| Lane | Query shape | Catches |
|---|---|---|
| Clinical menu | "management of <condition> review", "treatment options" | Guideline-level options |
| Procedural | "recalcitrant <condition>", "second-line", "refractory" | Injections, device therapies |
| Community long-tail | "what finally worked", "<condition> years" in condition subreddits | Patient-discovered options |
| Adjacent transfer | Same intervention proven in a related tissue/condition | Untested-here options |

Target 15–30 raw candidates. **Exclude nothing here** — dubious entries get sorted out by
grading, never by omission.

### 1. Decompose into atomic claims

A gradeable claim is `intervention + specific outcome + population`. "Citrulline helps
tendons" is not gradeable. "Citrulline improves tendon healing in adults with tendinosis" is.

### 2. Outcome-first search, including nulls

For each claim search the **outcome**, not the mechanism, and run at least one explicit
null-result query ("X no effect", "X failed to improve").

### 3. Grade each claim

Build a JSON object per claim and pipe it through the scorer:

```bash
echo '{"claim":"...","outcome_type":"mechanism-only","best_study_tier":"in-vitro",
"population_match":"none","consistency":"mixed","n_studies":0,
"absence_reason":"untested-low-commercial-incentive","risk":"low","cost_per_month":12,
"reversibility":"immediate","community_frequency":"moderate"}' \
  | python3 plugins/research/skills/medical-evidence/scripts/grade_claim.py
```

Pass a JSON array to grade many at once (output is sorted by priority). Field values:
- `outcome_type`: `clinical-outcome` | `surrogate` | `mechanism-only`
- `best_study_tier`: `meta-analysis` | `systematic-review` | `rct` | `cohort` | `case-series` | `animal` | `in-vitro` | `none`
- `population_match`: `direct` | `adjacent` | `distant` | `none`
- `consistency`: `consistent` | `mixed` | `contradicted`
- `absence_reason` (required when evidence is thin): `tested-and-refuted` | `untested-low-commercial-incentive` | `untested-implausible` | `too-new`
- `risk`: `low` | `moderate` | `high`; `reversibility`: `immediate` | `slow` | `permanent`
- `community_frequency`: `high` | `moderate` | `low` | `none`

**Never guess an input.** If a field is unknown, search for it or mark it honestly
(`best_study_tier: none`, `absence_reason: too-new`). Feeding a rigor tool an assumption is
the failure mode this skill exists to prevent.

### 4. Population-transfer check

State the studied population and whether it transfers. Never state a dose without its source
population.

### 5. Interaction & antagonism check (hard gate)

Across the **combined** stack: does anything cancel another (anti-inflammatories blunt PRP),
add risk (stacked antiplatelet load, additive hypotension), or duplicate a pathway? Flag
items to pause around any procedure, with a window.

### 6. Rank by probability of meaningful benefit

Sort aggressively by expected value. `worth-trying-anyway` items rank on merit, not demoted
for being understudied. Show `community_frequency` alongside but never fold it into the score;
show `hype_risk` where set.

### 7. Rollout

Everything mutually safe starts **together, now**. Stage only (a) interaction/antagonism-flagged
items and (b) items needing titration. Note attribution loss as an accepted tradeoff.

### 8. Escalate (adversarial second pass)

If the question is pre-procedure, prescription-interacting, or a purchase decision, dispatch a
subagent to attack each surviving claim (where is the outcome evidence, does the population
match, is this a mechanism leap) before finalizing.

## Output contract

End every medical answer with a ranked ledger, not prose that buries the grades:

```
Rank | Candidate | Evidence 1-5 | Why absent | Risk/cost | Freq | Verdict | Hedge
```

Then three required sections: **Rollout** (now vs staged), **What would change this answer**
(per claim), **Take to a clinician** (prescription/procedural items and interactions).

## Guardrails

- Mechanism-only claims are never phrased as recommendations.
- No dose without its source population.
- Declare any failed/empty source; it caps the confidence of the whole answer.
- Enumerate before evaluating.
- Follow-up offers stay inside the asked scope.
- This skill sorts options to bring to a clinician; it does not replace one.
````

- [ ] **Step 2: Commit**

```bash
git add plugins/research/skills/medical-evidence/SKILL.md
git commit -m "docs(research): medical-evidence SKILL.md pipeline"
```

---

### Task 6: Wire into literature-review + version bump + docs + validate

**Files:**
- Modify: `plugins/research/skills/literature-review/SKILL.md`
- Modify: `plugins/research/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the `medical-evidence` skill (Task 5).

- [ ] **Step 1: Insert Step 3.5 into literature-review**

In `plugins/research/skills/literature-review/SKILL.md`, immediately before the `### Step 4: Score` heading, insert:

```markdown
### Step 3.5 (medical/scientific intent): Grade claims with medical-evidence

If intent is `medical` (or a scientific health question), invoke the `medical-evidence` skill
before scoring. It enumerates the full solution space, decomposes results into atomic claims,
and grades each with `grade_claim.py`. Its ranked ledger — not the raw source list — becomes
the backbone of the summary. Do not hand-wave a recommendation past it; a `mechanism-only` or
`marketing-claim` verdict must be reported as such.
```

- [ ] **Step 2: Bump plugin version and description**

In `plugins/research/.claude-plugin/plugin.json`, change `"version": "0.5.0"` to `"version": "0.6.0"` and append to the description string (before the closing quote): ` Includes medical-evidence: enumerate-then-grade rigor for health questions (three-axis claim grading, absence-reason tracking).`

- [ ] **Step 3: Update marketplace description**

In `.claude-plugin/marketplace.json`, in the `research` plugin's `description`, append before the closing quote: ` Health questions route through a medical-evidence rigor layer that enumerates options and grades claims by evidence, risk/cost, and community frequency.`

- [ ] **Step 4: Document the skill in CLAUDE.md**

In `CLAUDE.md`, in the `research plugin: skill composition` section under the "Trust + verification skills" list, add a bullet:

```markdown
   - `medical-evidence` — for health questions: enumerates the full solution space (clinical/procedural/community/adjacent lanes), decomposes into atomic claims, and grades each via `grade_claim.py` on three independent axes (evidence 1-5, risk/cost, community frequency) with an `absence_reason` that keeps "untested because unpatentable" distinct from "tested and refuted". Emits a ranked ledger + clinician hand-off. Invoked by `literature-review` for medical intent and standalone.
```

Also update the plugin count line near the top: change `two plugins` context if a skill count is stated for research (it says "9 skills") to `10 skills`.

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest plugins/research/skills/medical-evidence/tests/ -v`
Expected: PASS (20 passed)

- [ ] **Step 6: Validate the plugin manifest**

Run: `claude plugin validate plugins/research`
Expected: no errors. (If `claude` CLI is unavailable in the environment, confirm `plugin.json` and `marketplace.json` are valid JSON with `python -m json.tool` on each instead.)

- [ ] **Step 7: Commit**

```bash
git add plugins/research/skills/literature-review/SKILL.md plugins/research/.claude-plugin/plugin.json .claude-plugin/marketplace.json CLAUDE.md
git commit -m "feat(research): wire medical-evidence into literature-review; bump 0.6.0"
```

---

## Self-Review notes

- **Spec coverage:** §0 enumeration → Task 5 pipeline §0. Three-axis grading + absence_reason → Tasks 1–4. Verdict quadrants → Task 3 (all five, session fixtures). Interaction gate, rollout, escalation → Task 5 SKILL.md §5–§8. Output contract → Task 5. Guardrails → Task 5. Testing fixtures → Tasks 3–4. Wiring + version + docs → Task 6.
- **Regression invariant** (`mechanism-only` never `well-supported`): enforced twice — capped in `evidence_grade` (Task 1 test) and re-guarded in `classify` (requires `outcome_type == "clinical-outcome"`).
- **Deferred (YAGNI, per spec):** numeric-weight tuning beyond the fixtures, and a `references/claim-grades.json` corpus.
