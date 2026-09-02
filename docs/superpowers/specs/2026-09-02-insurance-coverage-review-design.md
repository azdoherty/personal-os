# Insurance `coverage-review` skill — design

**Date:** 2026-09-02
**Status:** Approved for implementation

## Problem

At policy renewal, the user shops multiple carriers for home, auto, umbrella, jewelry, and life
insurance and wants to (a) compare quotes apples-to-apples and (b) decide the *right amount* of
coverage for each line, not just the cheapest premium. Quotes look comparable on price but hide big
differences in limits, deductibles, replacement-cost vs actual-cash-value, and endorsements. The
user also has gaps (currently no life insurance, paying ~$5k/yr for home + auto through Travelers).

This project builds a reusable Claude Code skill that bakes in insurance best practices so every
renewal review is thorough and consistent.

## Goals

- Compare 2+ quotes per line apples-to-apples, surfacing every substantive difference.
- Judge each line's coverage against the user's actual financial exposure (adequacy), not price alone.
- Account for hyperlocal factors (state-mandated coverages/minimums, catastrophe exposure and
  deductibles, local rebuild costs, carrier-availability dynamics) via a live localization phase.
- Perform a gap analysis: flag missing/under-carried lines (life, umbrella, disability) sized to the profile.
- Weigh carrier quality (claims reputation, financial strength), not just price.
- Produce a clear verdict with recommended coverage *targets* and a prioritized action list.

## Non-goals

- No stored financial profile / database. Stateless: profile is re-collected each run; no PII on disk.
- No scripts or computation engine. Quotes are unstructured (PDF/text/photos); judgment is prose-driven.
  The few formulas (DIME, umbrella sizing, dwelling replacement estimate) are computed inline.
- Not licensed financial or insurance advice. The skill surfaces best practices and reasoning; the
  user (and their agent) make the final call.
- No automatic file output. Deliver in-chat markdown; only save a report if the user asks.

## Approach (chosen)

**A — one skill + two reference files.** Mirrors the existing `roofing-quote-comparison` skill's
proven prose+reference shape (a process-driven `SKILL.md` plus a domain glossary), scaled from one
domain to six insurance lines. Rejected alternatives: (B) a multi-skill plugin, which fragments one
continuous renewal conversation and adds maintenance surface; (C) a monolithic `SKILL.md` with all
content inline, which bloats the always-loaded skill body and buries the reference knowledge.

## Architecture

New plugin **`insurance`** registered in `.claude-plugin/marketplace.json`, containing a single skill
**`coverage-review`**. No scripts.

```
plugins/insurance/
  .claude-plugin/plugin.json
  skills/coverage-review/
    SKILL.md
    reference/
      coverage-playbook.md
      localization.md
      carrier-quality.md
```

### Component responsibilities

- **`SKILL.md`** — trigger + process. Drives the 7-step flow, points to the reference files, lists
  common mistakes. Kept lean so the frontmatter description triggers reliably and the body doesn't
  duplicate the reference content.
- **`reference/coverage-playbook.md`** — the per-line knowledge base. One section per line
  (Home / Auto / Umbrella / Jewelry / Life / Other). Each section has three parts: **fields to
  extract** from a quote, **adequacy target + sizing formula**, and **red flags**. Each section also
  carries a **localize hook** naming which of its targets shift by state/region (e.g. auto minimums
  and mandatory coverages, home catastrophe deductibles, dwelling rebuild cost).
- **`reference/localization.md`** — the hyperlocal research playbook. Enumerates the location-driven
  dimensions to pin down (state-mandated coverages & minimums incl. no-fault/PIP and UM/UIM mandates;
  catastrophe exposure & special deductibles — hurricane/wind-hail/named-storm, flood zone, wildfire,
  earthquake, sinkhole; local rebuild cost per square foot; state carrier-availability dynamics such
  as non-renewals and FAIR/residual-market plans), the queries/sources to use, and how to feed the
  findings into the adequacy check. Uses the `research` plugin's `web-search` for live local info;
  state/region tables are **not** hard-coded (they go stale) — they are researched each run.
- **`reference/carrier-quality.md`** — how to judge a carrier: NAIC complaint index and AM Best
  financial-strength methodology, plus when/how to hand off to the `research` plugin
  (`literature-review` / `brand-check`) for live carrier reputation.

## SKILL.md process (data flow)

1. **Profile (stateless intake).** Ask for, and skip anything already provided: net worth (asset
   breakdown incl. home equity, investments, cash), gross income, dependents, mortgage balance +
   home value, other major assets, and current policies/premiums. Used to size every recommendation.
   Also capture **location** (state + ZIP/metro) — the trigger for step 2.
2. **Localize (hyperlocal research).** Per `localization.md`, research the user's state and region:
   state-mandated coverages & minimum limits (no-fault/PIP, UM/UIM mandates), catastrophe exposure &
   special deductibles (hurricane/wind-hail/named-storm, flood zone, wildfire, earthquake, sinkhole),
   local rebuild cost per square foot, and state carrier-availability dynamics. Uses the `research`
   plugin's `web-search`. Output is a short "local context" note that parameterizes the adequacy
   check — e.g. "FL: expect a separate hurricane deductible; flood is excluded, needs NFIP/private."
3. **Intake quotes.** For each supplied quote, extract the per-line fields from
   `coverage-playbook.md` into a markdown comparison table (one column per carrier, one row per
   field). Mark anything unstated as `not specified` — never infer inclusion from a competitor.
   Home + auto are available now; umbrella + jewelry are pending and slotted in when supplied.
4. **Adequacy check.** Judge each line against the playbook's target/formula **as adjusted by the
   step-2 local context**: home = replacement cost (+ extended/guaranteed, ordinance-or-law,
   replacement-cost-not-ACV contents, water backup, region-appropriate catastrophe/flood coverage);
   auto = the greater of the state minimum and the 100/300/100 floor, 250/500 with assets, UM/UIM as
   high as liability (and any state-mandated PIP); umbrella = net worth + a few years of future
   income, with underlying-limit requirements; jewelry = schedule items ≥ ~$2k with appraisal /
   agreed-value; life = DIME or income-replacement, term over whole.
5. **Carrier quality.** Weigh NAIC complaint index + AM Best per `carrier-quality.md`; hand off to
   the `research` plugin for live reputation on the specific carriers being compared.
6. **Gap analysis.** Flag missing/under-carried lines sized to the profile — **life** (user has
   none), **umbrella**, and **long-term disability** (the commonly-missed income-protection line),
   plus any other relevant line (e.g. flood/earthquake surfaced in step 2) noted in the Other section.
7. **Verdict.** Apples-to-apples price comparison; where a cheaper quote cuts a real corner; where a
   pricier quote's premium isn't earned; recommended coverage **targets** per line; a prioritized
   action list. Deliver in chat; offer to save a report only if asked.

## Reference content — best practices to bake in

Sourced from III, Consumer Reports, NerdWallet, Policygenius, Kiplinger, Bogleheads, White Coat
Investor (research performed 2026-09-02).

**Cross-line principle:** compare apples-to-apples (same limits/deductibles; pull each carrier's
declarations page); cheaper premiums usually mean lower limits, higher deductibles, or ACV-not-RC.

**Home** — insure to replacement cost (not market value or loan balance). Dwelling (Cov A) = full
rebuild; add extended replacement cost (+25–50% buffer) and guaranteed replacement cost if offered;
ordinance-or-law default ~10% is thin for older homes (bump to 25–50%); personal property on
replacement cost not ACV; water/sewer backup endorsement; adequate loss-of-use; liability (Cov E)
≥ $300k to sit under an umbrella.

**Auto** — III floor 100/300/100; ≥ 250/500/100 with real assets (and required under an umbrella);
UM/UIM treated as mandatory and set as high as liability (~1 in 7 drivers uninsured); deductibles are
the premium lever, raised only to what's affordable out of pocket.

**Umbrella** — $1M increments (~$150–300/M/yr); size to net worth + a few years future income (asset
*and* wage-garnishment exposure), not a rigid "= net worth"; requires underlying limits
(typically $300k home liability, 250/500 auto).

**Jewelry** — standard home caps jewelry theft ~$1,500; schedule items ≥ ~$2,000 (floater/
endorsement): no deductible, covers accidental loss, needs appraisal; heirlooms on agreed-value.

**Life** — term is the default (20-yr $500k term ≈ $26/mo vs ≈ $451/mo whole; skip whole/cash-value
in almost all cases); size via DIME (Debt + Income×years + Mortgage + Education) or income ÷ 4–5%,
roughly 10–15× income.

**Other** — **long-term disability** (protects the income that funds everything; more likely used
than life insurance), and situational lines (flood/earthquake where applicable). Surfaced as
"insurance to consider carrying," sized qualitatively.

**Localization (hyperlocal)** — insurance is state- and region-specific; adequacy targets must be
adjusted to location before judging a quote. Dimensions to research live (never hard-coded):
- **State-mandated coverages & minimums** — required liability minimums, no-fault/PIP states,
  UM/UIM mandates, and other state-required coverages (compare the state minimum against the
  100/300/100 floor and take the greater).
- **Catastrophe exposure & special deductibles** — hurricane / wind-hail / named-storm percentage
  deductibles, flood zone (flood is excluded from home policies → NFIP/private), wildfire,
  earthquake (excluded → separate policy), sinkhole; drives which endorsements/separate policies are
  non-optional in that region.
- **Local rebuild cost per square foot** — parameterizes the dwelling replacement-cost sanity check.
- **State carrier-availability dynamics** — non-renewal waves, insurers exiting a state, FAIR/
  residual-market plans; affects who to shop and whether a cheap quote is durable.

**Carrier quality** — NAIC complaint index (1.0 = industry average; higher = more complaints per
premium dollar) for claims-service reputation; AM Best rating (A/A+/A++ strong) for financial
strength / ability to pay claims. A cheap quote from a poor-claims or weak-balance-sheet carrier gets
flagged. Hand off to `research` plugin for anecdotal reputation (Reddit claims experiences, etc.).

## Testing / verification

No automated tests (prose skill, no scripts — consistent with the `research` plugin's convention).
Verification is manual:

- `claude plugin validate plugins/insurance` passes.
- `claude plugin validate .` (marketplace) passes.
- Dry-run the skill against the user's real Travelers home + auto quotes: confirm it runs the
  localization step for the user's state, produces the comparison tables, adequacy verdicts adjusted
  for local context, gap analysis (life/umbrella/disability), and an action list, and that it
  correctly marks unsupplied fields `not specified`.

## Risks / open questions

- **Regional/temporal drift** in dollar figures and rules (construction cost/sq-ft, state minimums,
  catastrophe-deductible norms). Mitigation: the playbook teaches *methods and relative comparison*
  (compare across the user's own quotes), not fixed external benchmarks, and the localization step
  researches state/region specifics live rather than baking in stale tables.
- **Not-advice boundary.** The skill must frame outputs as decision support, not licensed advice.
