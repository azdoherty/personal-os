# `medical-evidence` skill — design

**Date:** 2026-08-16
**Plugin:** `research` (bump 0.5.0 → 0.6.0)
**Status:** design approved, pending implementation plan

## Problem

The `research` plugin treats `medical` as one row in `literature-review`'s intent table: it
picks sources (PubMed first, patient subreddits) and says "flag personal anecdotes vs
evidence." That is source selection, not rigor. `source-trust` scores *sources*; nothing
scores *claims*.

A long health-research session exposed the consequences:

1. **Mechanism-to-recommendation leaps.** L-citrulline has meta-analysis support for blood
   pressure and *zero* tendon studies. It entered a recommended stack anyway. Same shape of
   error for moringa and urolithin A.
2. **Assert-then-verify.** Four claims in one pre-procedure answer (avoid ice, hydration
   boosts platelet yield, greasy food is fine, coffee is fine) were wrong or overstated and
   were corrected only because the user explicitly asked for a double-check.
3. **A rigor tool fed an assumption.** `brand_check.py` was run with `--integrity-hits 0`,
   returning "legitimate / 70" for a vendor with a 2023 federal guilty plea. The tool was
   fine; the input was a guess.
4. **Confidence outran inputs.** A polished summary with a dosing table was produced while
   Reddit returned off-topic results and the HN source failed silently (`jq` not installed).
   The failure became a footnote instead of capping confidence.
5. **Doses stated without provenance.** "300–600 mg ashwagandha" presented as settled rather
   than traced to a trial population.
6. **Candidate set supplied by the user.** The session graded what the user brought
   (moringa, Mito Pure, NAD+, arginine, kava). The higher-value options — topical GTN,
   ESWT, prolotherapy, blood-flow-restriction training — surfaced late and only after the
   user pushed. Every query was confirmatory ("does X help?"), never enumerative
   ("what are all the options for this condition?").

## Goals

- Enumerate the full solution space for a health problem before evaluating anything.
- Grade each candidate reproducibly, separating *evidence strength* from *risk/cost* and from
  *community frequency*.
- Preserve plausible, cheap, low-risk, structurally-understudied options instead of
  discarding them for lacking trials.
- Catch interactions and antagonism across a combined stack.
- Rank by probability of meaningful benefit and produce a deployable rollout.

## Non-goals

- Diagnosis, or replacing a clinician. Prescription and procedural items route to a
  clinician by design.
- Optimizing for scientific attribution. The user explicitly traded attribution for speed
  (see Rollout).
- A general-purpose evidence engine. Scope is health/medical questions inside `research`.

## Key design decision: three independent axes

A single 1–5 evidence score conflates "tested and refuted" with "nobody ever tested it."
Those are different facts and the second is often an artifact of funding, not biology —
unpatentable compounds do not attract phase-3 trials. Collapsing them hides exactly the
options the user wants surfaced.

The same reasoning is also the standard pitch of supplement marketing, so permissiveness
alone is not acceptable either. Resolution: grade on three axes that are never merged.

| Axis | Question |
|---|---|
| `evidence_grade` (1–5) | What do human outcome studies actually show? |
| `risk_cost_grade` | What does it cost to try this and be wrong? |
| `community_frequency` | How often do people with this condition independently converge on it? |

Plus a required `absence_reason` whenever evidence is thin:
`tested-and-refuted` | `untested-low-commercial-incentive` | `untested-implausible` | `too-new`

`absence_reason` is what separates "cheap and unstudied" from "promoted and baseless."

## Architecture

```
plugins/research/skills/medical-evidence/
  SKILL.md
  scripts/grade_claim.py     # stdlib-only; JSON on stdin -> graded JSON on stdout
```

**Invocation, both paths:**
- `literature-review` calls it as a **mandatory step** when intent is `medical` (new Step 3.5,
  before scoring).
- **Standalone**, for any health question not warranting a full review. This path matters
  most: the session's errors occurred in follow-up questions that never entered
  `literature-review`.

Consistent with house style: scripts compute scores, SKILL.md orchestrates, stdlib only.

## Pipeline

### Step 0 — Candidate enumeration

Search the *problem*, not the solution. Confirmatory queries ("does X help Y?") can only
validate a candidate the user already named; enumerative queries return the menu.

Four lanes, deliberately including the long tail:

| Lane | Query shape | Catches |
|---|---|---|
| Clinical menu | "management of \<condition\>", "treatment options review" | Guideline-level options |
| Procedural | "recalcitrant \<condition\>", "second-line", "refractory" | GTN, ESWT, prolotherapy, Tenex |
| Community long-tail | "what finally worked", "\<condition\> years" in condition subreddits | Patient-discovered options |
| Adjacent transfer | Same intervention proven in a related tissue/condition | Untested-here options |

Target 15–30 raw candidates. **Nothing is excluded at this stage** — dubious entries
(BPC-157, kratom) are enumerated and then sorted by grading, never by omission.

### Step 1 — Decompose into atomic claims

A gradeable claim is `intervention + specific outcome + population`. "Citrulline helps
tendons" is not gradeable. "Citrulline improves tendon healing in adults with tendinosis" is.

### Step 2 — Outcome-first search, including nulls

For each claim, search the **outcome**, not the mechanism, and run at least one explicit
null-result query ("X no effect", "X failed to improve"). This single step would have caught
citrulline and moringa immediately.

### Step 3 — Grade via `grade_claim.py`

**Inputs:** `claim`, `outcome_type` (`clinical-outcome`|`surrogate`|`mechanism-only`),
`best_study_tier` (`meta-analysis`|`systematic-review`|`rct`|`cohort`|`case-series`|`animal`|`in-vitro`|`none`),
`population_match` (`direct`|`adjacent`|`distant`|`none`), `consistency`
(`consistent`|`mixed`|`contradicted`), `n_studies`, `absence_reason`, `risk`
(`low`|`moderate`|`high`), `cost_per_month`, `reversibility`
(`immediate`|`slow`|`permanent`), `community_frequency` (`high`|`moderate`|`low`|`none`).

**Outputs:** `evidence_grade` (1–5, 5 = strongest), `risk_cost_grade` (1–5, 5 = safest and
cheapest, so both axes read "higher is better"), `community_frequency`, `verdict_quadrant`,
`hype_risk` (true when frequency is high and evidence is nil), `required_hedge` (exact
language that must appear in the summary), `what_would_change_this`.

**Verdict quadrants:**

| Quadrant | Definition | Session example |
|---|---|---|
| `well-supported` | Human outcome evidence, population matches | Collagen + vitamin C, creatine, loading |
| `worth-trying-anyway` | Weak evidence **and** plausible mechanism, low risk, low cost, reversible, `untested-low-commercial-incentive` | L-citrulline, glycine |
| `unproven-and-costly` | Weak evidence, material expense | Urolithin A, NAD+ precursors |
| `marketing-claim` | Untested, promoted, no mechanism for *that specific* claim | Moringa "builds tendons" |
| `avoid` | Refuted, or risk/irreversibility dominates | BPC-157, kratom |

`worth-trying-anyway` is a first-class result, not a consolation tier, and ranks on its
merits in Step 6.

### Step 4 — Population transfer check

State the studied population and whether it transfers. Rats, elderly sarcopenia cohorts, and
trained athletes are not interchangeable with the user. Never state a dose without its
source population.

### Step 5 — Interaction and antagonism check (hard gate)

Across the *combined* stack, not per item:
- **Antagonism** — does A cancel B? (Anti-inflammatories blunt PRP; this is the canonical case.)
- **Additive risk** — stacked antiplatelet load, additive sedation, compounded hypotension
  (e.g. citrulline plus a GTN patch), shared hepatic burden.
- **Redundancy** — several items on one pathway yield one effect, not several.
- **Procedure timing** — items to pause around an injection or surgery, with a window.

This gate is non-negotiable and is the only thing permitted to delay a rollout.

### Step 6 — Rank by probability of meaningful benefit

Sort by expected value: evidence × plausible effect size ÷ risk/cost. Ranking is
**aggressive, not conservative** — the objective is maximizing the chance of winning, not
minimizing the chance of recommending something unproven. `community_frequency` is displayed
alongside but never folded into the score; `hype_risk` is shown where it applies.

### Step 7 — Rollout plan

**Fast parallel batching.** All mutually-safe items begin **together, immediately**. Only two
categories are staged:
1. Items flagged by Step 5 (interaction or antagonism).
2. Items requiring titration (e.g. GTN patches and dose-dependent headache).

Attribution loss is recorded as an explicit, accepted user tradeoff after years of a chronic
problem. Partial attribution is recovered free from the user's existing daily-log habit.

### Step 8 — Escalation trigger

Run an adversarial second pass (subagent that attacks each surviving claim: where is the
outcome evidence, does the population match, is this a mechanism leap) when the question is:
- pre-procedure,
- interacting with a prescription, or
- a purchase decision.

Not run on routine questions; it roughly doubles cost and latency.

## Output contract

Every medical answer ends with a ranked ledger rather than prose that buries the grades:

```
Rank | Candidate | Evidence 1-5 | Why absent | Risk/cost | Freq | Verdict | Hedge
```

Followed by three required sections:
- **Rollout** — what starts now (parallel), what is staged and why.
- **What would change this answer** — per claim.
- **Take to a clinician** — prescription/procedural items, interactions, and anything the
  skill declined to recommend directly.

## Guardrails

Each maps to an observed failure:

| Guardrail | Failure it prevents |
|---|---|
| Mechanism-only claims may never be phrased as recommendations | citrulline in the stack |
| No dose without its source population | "300–600 mg" stated bare |
| Tool failures are declared and cap stated confidence | silent `jq` failure, empty Reddit |
| Never populate a rigor tool with a guessed input; search it or mark it unknown | `--integrity-hits 0` |
| Enumerate before evaluating | GTN/ESWT/BFR surfaced late |
| Follow-up offers stay inside the asked scope | drift to kratom, sled design |
| Prescription/procedural items route to a clinician, never a recommendation | GTN dosing |

## Testing

`grade_claim.py` is pure and deterministic, so it is unit-testable. Fixture cases drawn from
this session, asserting the expected quadrant:

- collagen + vitamin C → `well-supported`
- L-citrulline for tendon → `worth-trying-anyway`, `mechanism-only`, hedge present
- moringa for tendon → `marketing-claim`
- urolithin A for tendon → `unproven-and-costly`
- BPC-157 → `avoid`, `hype_risk: true`
- kava for relaxation → `well-supported` on anxiety, with risk flag driving `risk_cost_grade`

Regression guarantee: a `mechanism-only` input can never produce a `well-supported` verdict.

## Open questions for implementation

- Exact numeric weights inside `grade_claim.py` (start simple and transparent; tune against
  the fixtures above).
- Whether a `references/claim-grades.json` corpus of pre-graded common claims is worth
  adding later to avoid re-litigating repeat questions. Deferred as YAGNI for v1.
