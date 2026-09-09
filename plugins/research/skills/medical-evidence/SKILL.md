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
- `cost_per_month`: approximate USD/month — feeds the risk/cost axis (>50 marks an item costly)
- `n_studies`: integer count of supporting human studies (0 floors evidence to 1)

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
