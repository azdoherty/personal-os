---
name: coverage-review
version: 0.1.0
description: Use when the user wants to review insurance quotes at renewal, compare carriers, or decide how much coverage to carry — home, auto, umbrella, jewelry, life, or "what insurance should I have". Compares quotes apples-to-apples, judges coverage adequacy against the user's financial exposure and hyperlocal (state/region) factors, flags gaps (life, umbrella, disability), and weighs carrier claims reputation and financial strength.
allowed-tools:
  - Read
  - WebSearch
  - Skill
  - Task
triggers:
  - review my insurance quotes
  - compare these insurance quotes
  - how much coverage do i need
  - is my home insurance enough
  - am i paying too much for insurance
  - should i switch insurance carriers
  - what insurance should i have
---

# Insurance Coverage Review

## Overview

At renewal, insurance quotes look apples-to-apples on premium alone but hide big differences in
limits, deductibles, replacement-cost vs actual-cash-value, and endorsements — and the *right*
amount of coverage depends on the user's assets, income, dependents, and **where they live**
(state mandates and regional catastrophe exposure). The job: extract every substantive difference
between quotes, judge each line against the user's real exposure adjusted for local context, flag
missing lines, weigh carrier quality, and deliver a clear verdict with recommended coverage targets.

This is decision support, not licensed insurance or financial advice — say so in the verdict.

## When to Use

- User has one or more insurance quotes (any line) and wants them compared or sanity-checked.
- User asks how much coverage to carry, whether they're over/under-insured, or what insurance to have.

Not for: filing claims, or questions answerable without reviewing coverage.

## Process

Work through these steps in order. Skip nothing, but move fast through steps where the user has
already supplied the information.

1. **Profile (ask, don't store).** Collect — and skip anything already given — net worth with an
   asset breakdown (home equity, investments, cash), gross household income, number/ages of
   dependents, mortgage balance + home value, other major assets, and current policies + premiums.
   Also ask for **recent claims history** (any home/auto claims in the last ~5–7 years) and any
   **employer group coverage** (life, LTD/STD, health) — both change the analysis later. Capture
   **location: state + ZIP or metro** — this drives step 2. Do not write any of this to disk.

2. **Localize (hyperlocal research).** Follow `reference/localization.md`. Research the user's state
   and region for: state-mandated coverages & minimum limits (no-fault/PIP, UM/UIM mandates),
   catastrophe exposure & special deductibles (hurricane/wind-hail/named-storm, flood zone, wildfire,
   earthquake, sinkhole), local rebuild cost per square foot, and carrier-availability dynamics.
   Prefer the `research` plugin's `web-search` skill; fall back to `WebSearch`. Produce a short
   **local context note** that parameterizes the adequacy check.

3. **Intake quotes.** For each quote, use `Read` on the file — it handles PDFs (read all pages) and
   photos. For a scan or photo where a number is illegible or ambiguous, do not guess: ask the user to
   confirm it before it feeds a sizing formula. Extract the per-line fields listed in
   `reference/coverage-playbook.md` into a markdown comparison table — one column per carrier, one
   row per field. Mark anything not stated as `not specified`; never infer inclusion because a
   competitor included it. Home + auto may be present now; add umbrella/jewelry columns when supplied.
   For a **line whose quote hasn't arrived yet** (e.g. umbrella, jewelry), still compute its adequacy
   **target** in step 4 so the user has a number to judge the pending quote against when it lands.

4. **Adequacy check.** Judge each line against the target/formula in `reference/coverage-playbook.md`,
   **adjusted by the step-2 local context** (e.g. auto liability = the greater of the state minimum
   and the 100/300/100 floor; home must carry region-appropriate catastrophe/flood coverage). Show
   the sizing math (dwelling replacement estimate, umbrella = net worth + future income, life DIME).

5. **Carrier quality.** Apply `reference/carrier-quality.md`: weigh each carrier's NAIC complaint
   index and AM Best financial-strength rating, and hand off to the `research` plugin
   (`literature-review` / `brand-check`) for live reputation on the specific carriers being compared.
   A cheap quote from a poor-claims or financially weak carrier gets flagged.

6. **Gap analysis.** Flag missing or under-carried lines sized to the profile: **life** (income
   replacement / DIME), **umbrella** (net worth + future income), and **long-term disability** (the
   commonly-missed income-protection line), plus any situational line surfaced in step 2 (e.g. flood,
   earthquake). See the Other section of the playbook.

7. **Verdict.** Deliver in chat: the apples-to-apples price comparison, where a cheaper quote cuts a
   real corner, where a pricier quote's premium isn't earned, recommended coverage **targets** per
   line, and a prioritized action list. Compare **total household cost of bundling** (home + auto,
   sometimes umbrella, with one carrier) against cherry-picking the cheapest quote per line — bundling
   discounts run ~5–25%, so the per-line-cheapest set can cost more once the discount is lost. If the
   profile shows recent claims, note that a renewal hike may be claims-driven, and that any recommended
   switch will trigger a new carrier's CLUE-report pull (which can reprice or decline). Note the
   not-advice framing. Offer to save a report file only if the user asks.

## Common Mistakes

- Treating `not specified` as "included" or "excluded" — always flag it as unknown in the verdict.
- Comparing premiums without normalizing limits/deductibles (pull each carrier's declarations page).
- Judging adequacy without the local context — e.g. missing a state-mandated coverage, or a hurricane
  or flood exposure that makes an endorsement/separate policy non-optional.
- Letting a bigger limit number win without checking what it actually covers (replacement cost vs
  ACV; per-item vs blanket jewelry sublimit).
- Recommending whole life by default (term is the default), or sizing umbrella at a rigid "= net worth".
- Declaring a winner on price alone when a carrier has a poor NAIC complaint index or weak AM Best rating.

**REQUIRED REFERENCES:** Read `reference/coverage-playbook.md` (per-line extraction + adequacy),
`reference/localization.md` (the hyperlocal research step), and `reference/carrier-quality.md`
(carrier judgment) before writing the verdict.
