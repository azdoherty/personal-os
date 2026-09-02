# Insurance `coverage-review` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new `insurance` plugin containing one stateless, prose-driven `coverage-review` skill that compares insurance quotes apples-to-apples and judges coverage adequacy across home, auto, umbrella, jewelry, life, and other lines — adjusted for the user's hyperlocal (state/region) context.

**Architecture:** A Claude Code plugin registered in the marketplace, holding a single skill. The skill's `SKILL.md` drives a 7-step process (profile → localize → intake → adequacy → carrier quality → gap analysis → verdict) and delegates domain knowledge to three reference files. No scripts, no stored PII; the localization step and carrier-reputation handoff use the existing `research` plugin's skills. This mirrors the existing `roofing-quote-comparison` skill's proven prose+reference shape.

**Tech Stack:** Markdown only (SKILL.md + reference `.md` files), JSON manifests. No Python, no dependencies. Validation via `claude plugin validate`.

## Global Constraints

- **No scripts, no dependencies.** Content is Markdown + JSON only. Do not add a `scripts/` dir or any Python.
- **Stateless / no stored PII.** The skill must not write the user's financial profile or quote data to disk. Profile is re-collected each run. Output is in-chat markdown; a saved report is produced *only* if the user explicitly asks.
- **Not licensed advice.** All outputs are framed as decision support, not licensed financial/insurance advice.
- **Localize live, never hard-code.** State/region specifics (minimums, catastrophe deductibles, rebuild costs, carrier availability) are researched live each run — reference files teach *method and dimensions*, never fixed state tables that go stale.
- **Manifest is authoritative for versions.** Plugin version lives in `plugins/insurance/.claude-plugin/plugin.json`; SKILL.md frontmatter `version` is informational and must match.
- **Author block copied verbatim from sibling plugins:** `{ "name": "azdoh", "email": "your-email@example.com" }`.
- **Marketplace category:** `productivity` (matches siblings).
- **Reference files are REQUIRED reading**, invoked by name from SKILL.md the way `roofing-quote-comparison` cites its glossary.

---

## File Structure

```
plugins/insurance/
  .claude-plugin/plugin.json                     # Task 1 — plugin manifest
  skills/coverage-review/
    SKILL.md                                      # Task 2 — trigger + 7-step process
    reference/
      coverage-playbook.md                        # Task 3 — per-line extract/adequacy/red-flags
      localization.md                             # Task 4 — hyperlocal research playbook
      carrier-quality.md                          # Task 5 — NAIC/AM Best + research handoff
.claude-plugin/marketplace.json                   # Task 1 — append insurance entry
CLAUDE.md                                          # Task 6 — document the new plugin
```

Responsibilities:
- **plugin.json / marketplace.json** — register the plugin so Claude Code discovers it.
- **SKILL.md** — the always-loaded trigger + the process an agent follows; stays lean and points to references.
- **coverage-playbook.md** — per-line (Home/Auto/Umbrella/Jewelry/Life/Other) knowledge: fields to extract, adequacy target + sizing formula, red flags, and a localize hook.
- **localization.md** — the dimensions and queries for the hyperlocal research step.
- **carrier-quality.md** — how to judge a carrier (NAIC complaint index, AM Best) and when to hand off to the `research` plugin.

---

## Task 1: Register the plugin (manifest + marketplace)

**Files:**
- Create: `plugins/insurance/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json` (append one object to the `plugins` array)

**Interfaces:**
- Produces: a discoverable plugin named `insurance`. Later tasks add its skill and references; the plugin dir path `plugins/insurance` is fixed here.

- [ ] **Step 1: Create the plugin manifest**

Create `plugins/insurance/.claude-plugin/plugin.json` with exactly:

```json
{
  "name": "insurance",
  "version": "0.1.0",
  "description": "Insurance renewal helper: compare home/auto/umbrella/jewelry/life quotes apples-to-apples and judge coverage adequacy against your financial exposure, adjusted for hyperlocal (state/region) factors. Flags gaps (life, umbrella, disability), weighs carrier claims reputation and financial strength, and hands off to the research plugin for live carrier reputation. Stateless, no stored PII.",
  "author": { "name": "azdoh", "email": "your-email@example.com" }
}
```

- [ ] **Step 2: Append the marketplace entry**

In `.claude-plugin/marketplace.json`, add this object as the **last** element of the `plugins` array (add a comma after the `workout` entry's closing brace):

```json
    {
      "name": "insurance",
      "description": "Compare insurance quotes apples-to-apples and choose the right coverage across home, auto, umbrella, jewelry, and life — adjusted for state/region specifics. Flags missing lines (life, umbrella, disability), weighs carrier claims reputation + financial strength, and hands off to the research plugin for live carrier reputation. Stateless prose skill, no stored PII.",
      "source": "./plugins/insurance",
      "category": "productivity"
    }
```

- [ ] **Step 3: Validate the marketplace JSON parses**

Run: `python -c "import json; json.load(open('.claude-plugin/marketplace.json'))" && echo OK`
Expected: `OK` (no JSON error). If it errors, you likely missed the comma after the `workout` entry.

- [ ] **Step 4: Validate the plugin manifest**

Run: `python -c "import json; json.load(open('plugins/insurance/.claude-plugin/plugin.json'))" && echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add plugins/insurance/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "feat(insurance): scaffold and register insurance plugin"
```

---

## Task 2: `SKILL.md` — trigger + 7-step process

**Files:**
- Create: `plugins/insurance/skills/coverage-review/SKILL.md`

**Interfaces:**
- Consumes: the plugin registered in Task 1.
- Produces: the `coverage-review` skill. References three files created in Tasks 3–5 by relative path (`reference/coverage-playbook.md`, `reference/localization.md`, `reference/carrier-quality.md`); those paths are fixed here.

- [ ] **Step 1: Write the full SKILL.md**

Create `plugins/insurance/skills/coverage-review/SKILL.md` with exactly this content:

````markdown
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
   Also capture **location: state + ZIP or metro** — this drives step 2. Do not write any of this to
   disk.

2. **Localize (hyperlocal research).** Follow `reference/localization.md`. Research the user's state
   and region for: state-mandated coverages & minimum limits (no-fault/PIP, UM/UIM mandates),
   catastrophe exposure & special deductibles (hurricane/wind-hail/named-storm, flood zone, wildfire,
   earthquake, sinkhole), local rebuild cost per square foot, and carrier-availability dynamics.
   Prefer the `research` plugin's `web-search` skill; fall back to `WebSearch`. Produce a short
   **local context note** that parameterizes the adequacy check.

3. **Intake quotes.** For each quote (PDF/text/photo), extract the per-line fields listed in
   `reference/coverage-playbook.md` into a markdown comparison table — one column per carrier, one
   row per field. Mark anything not stated as `not specified`; never infer inclusion because a
   competitor included it. Home + auto may be present now; add umbrella/jewelry columns when supplied.

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
   line, and a prioritized action list. Note the not-advice framing. Offer to save a report file
   only if the user asks.

## Common Mistakes

- Treating `not specified` as "included" or "excluded" — always flag it as unknown in the verdict.
- Comparing premiums without normalizing limits/deductibles (pull each carrier's declarations page).
- Judging adequacy without the local context — e.g. missing a state-mandated coverage, or a hurricane
  or flood exposure that makes an endorsement/separate policy non-optional.
- Letting a longer warranty/limit number win without checking what it actually covers (replacement
  cost vs ACV; manufacturer vs workmanship; per-item vs blanket jewelry sublimit).
- Recommending whole life by default (term is the default), or sizing umbrella at a rigid "= net worth".
- Declaring a winner on price alone when a carrier has a poor NAIC complaint index or weak AM Best rating.

**REQUIRED REFERENCES:** Read `reference/coverage-playbook.md` (per-line extraction + adequacy),
`reference/localization.md` (the hyperlocal research step), and `reference/carrier-quality.md`
(carrier judgment) before writing the verdict.
````

- [ ] **Step 2: Verify the plugin now validates end-to-end**

Run: `claude plugin validate plugins/insurance`
Expected: validation passes (no errors). If `claude` is unavailable in this environment, fall back to: `python -c "import re,sys; t=open('plugins/insurance/skills/coverage-review/SKILL.md').read(); assert t.startswith('---'); assert 'name: coverage-review' in t; print('OK')"` → `OK`.

- [ ] **Step 3: Verify the whole marketplace validates**

Run: `claude plugin validate .`
Expected: passes (fall back to the Task 1 JSON-parse checks if `claude` is unavailable).

- [ ] **Step 4: Commit**

```bash
git add plugins/insurance/skills/coverage-review/SKILL.md
git commit -m "feat(insurance): add coverage-review skill (7-step process)"
```

---

## Task 3: `reference/coverage-playbook.md` — per-line knowledge base

**Files:**
- Create: `plugins/insurance/skills/coverage-review/reference/coverage-playbook.md`

**Interfaces:**
- Consumes: referenced by `SKILL.md` step 3 (extract) and step 4 (adequacy).
- Produces: per-line sections each with **Extract / Adequacy target & formula / Red flags / Localize hook**. SKILL.md relies on these exact concepts existing.

- [ ] **Step 1: Write the playbook**

Create the file with exactly this content:

````markdown
# Coverage Playbook

Per-line reference for extracting quote fields and judging adequacy. Compare **apples-to-apples**:
same limits and deductibles across carriers (pull each carrier's declarations page). A cheaper
premium usually means lower limits, a higher deductible, or actual-cash-value (ACV) instead of
replacement cost. Adjust every target by the **local context** from `localization.md`.

Coverage *targets* below are methods and relative benchmarks, not guarantees — size to the user's
own profile and quotes, not to fixed external numbers.

## Home

**Extract:** carrier, premium, dwelling (Coverage A) limit, other structures (B), personal property
(C) limit **and whether replacement cost or ACV**, loss-of-use (D), personal liability (E), medical
payments (F), deductible(s) incl. any separate wind/hail/hurricane %, extended/guaranteed replacement
cost, ordinance-or-law %, water/sewer backup, service line, and any catastrophe endorsements or
exclusions (flood, earthquake).

**Adequacy target & formula:**
- Dwelling (A) = **replacement cost** (full rebuild), NOT market value or loan balance. Sanity-check:
  living area sq-ft × local rebuild cost/sq-ft (from `localization.md`).
- Add **extended replacement cost** (+25–50% buffer over A) and **guaranteed replacement cost** if
  the carrier offers it.
- **Ordinance-or-law**: default ~10% of A is thin for older homes; bump to 25–50% if the home is
  older or local codes have changed.
- Personal property (C) on **replacement cost, not ACV**.
- Add **water/sewer backup** endorsement.
- Liability (E) ≥ **$300,000** so it can sit under an umbrella; higher if assets warrant.
- Loss-of-use (D) adequate for local rebuild timelines.

**Red flags:** dwelling set to market/loan value; personal property on ACV; no extended replacement
cost; ordinance-or-law left at the ~10% default on an older home; missing water backup; liability
below $300k; a low premium achieved via a much higher deductible than the user carries today.

**Localize hook:** rebuild cost/sq-ft, hurricane/wind-hail/named-storm % deductibles, and whether
flood/earthquake are excluded (they usually are) all come from `localization.md`.

## Auto

**Extract:** carrier, premium, bodily-injury liability per-person/per-accident, property-damage
liability, uninsured/underinsured motorist (UM/UIM) limits, PIP/med-pay, comprehensive & collision
deductibles, and any rental/roadside/gap coverage.

**Adequacy target & formula:**
- Liability floor = **100/300/100** (III recommendation); carry **250/500/100** with real assets, and
  it's typically **required underneath an umbrella**. Take the **greater of** this and the state
  minimum from `localization.md`.
- **UM/UIM** treated as mandatory (≈1 in 7 drivers uninsured); set as high as liability.
- Include any **state-mandated PIP / no-fault** coverage (from `localization.md`).
- Deductibles (comp/collision) are the premium lever — raise only to what the user can pay out of pocket.

**Red flags:** liability at state minimum when assets are substantial; UM/UIM missing or far below
liability; a premium gap explained entirely by a higher deductible; dropping comp/collision on a car
still worth insuring.

**Localize hook:** state minimum limits, no-fault/PIP requirement, and UM/UIM mandate come from
`localization.md`.

## Umbrella

**Extract:** carrier, premium, umbrella limit, and the **underlying limits it requires** on home and
auto.

**Adequacy target & formula:**
- Size to **net worth + a few years of future income** (covers both asset seizure and wage
  garnishment), not a rigid "= net worth". Sold in **$1M increments** (~$150–300 per $1M per year).
- Requires underlying limits first: typically **$300k home liability** and **250/500 auto**. Confirm
  the home/auto quotes meet these before recommending an umbrella.

**Red flags:** recommending umbrella before underlying limits are raised to qualify; sizing far below
net worth + income exposure; ignoring wage-garnishment exposure for a high earner.

**Localize hook:** none material beyond the underlying auto/home minimums.

## Jewelry (and other valuables)

**Extract:** for each item — description, appraised value, whether scheduled (floater/endorsement) or
relying on the home policy's blanket jewelry sublimit; deductible; agreed-value vs replacement basis.

**Adequacy target & formula:**
- Standard home policies cap **jewelry theft at ~$1,500** (a per-category sublimit). Any single item
  worth **≥ ~$2,000** should be **scheduled** (floater/endorsement): no deductible, covers accidental
  loss (e.g. dropped down a drain), requires an **appraisal**.
- Heirlooms / hard-to-replace pieces: insure on an **agreed-value** basis.

**Red flags:** valuable jewelry left under the blanket sublimit; no current appraisal; replacement
basis where agreed-value is warranted for an heirloom.

**Localize hook:** none material.

## Life

**Extract (current coverage / quotes):** type (term vs whole/permanent), death benefit, term length,
premium, and any cash-value component.

**Adequacy target & formula:**
- **Term is the default.** Whole/permanent is dramatically more expensive for the same death benefit
  (illustratively, a 20-yr $500k term ≈ $26/mo vs ≈ $451/mo whole) — skip cash-value products in
  almost all cases.
- Size via **DIME**: **D**ebt (non-mortgage) + final expenses, **I**ncome × years of support needed,
  **M**ortgage payoff, **E**ducation (~+$100k per child). Cross-check against income-replacement
  (annual income ÷ 4–5%) and the 10–15× income rule of thumb.

**Red flags:** no coverage while others depend on the user's income (a mortgage + dependents is the
classic gap); whole life sold as an "investment"; term length shorter than the years of dependency.

**Localize hook:** none material.

## Other — insurance to consider carrying

- **Long-term disability (LTD):** protects the income that funds everything else and is **more likely
  to be used than life insurance** for a working-age earner. Check employer group LTD (often caps at
  ~60% of base salary, may be taxable) and whether a supplemental individual policy is warranted.
  Surface it whenever the user has earned income and dependents/obligations.
- **Situational lines** surfaced by `localization.md`: **flood** (NFIP or private — home policies
  exclude it; required in high-risk zones and worth considering in moderate ones), **earthquake**
  (separate policy where exposure exists), and similar region-specific perils.

Size these qualitatively (adequate group + supplement to reach a target income-replacement %); the
goal is to flag the gap and recommend a direction, not to price a policy.
````

- [ ] **Step 2: Sanity-check the file has all six line sections**

Run: `python -c "t=open('plugins/insurance/skills/coverage-review/reference/coverage-playbook.md').read(); [t.index(h) for h in ['## Home','## Auto','## Umbrella','## Jewelry','## Life','## Other']]; print('OK')"`
Expected: `OK` (raises `ValueError` if any heading is missing).

- [ ] **Step 3: Commit**

```bash
git add plugins/insurance/skills/coverage-review/reference/coverage-playbook.md
git commit -m "feat(insurance): add coverage-playbook reference"
```

---

## Task 4: `reference/localization.md` — hyperlocal research playbook

**Files:**
- Create: `plugins/insurance/skills/coverage-review/reference/localization.md`

**Interfaces:**
- Consumes: referenced by `SKILL.md` step 2 and by the "Localize hook" lines in the playbook.
- Produces: the four hyperlocal dimensions + queries + a local-context-note shape that step 4 consumes.

- [ ] **Step 1: Write the localization playbook**

Create the file with exactly this content:

````markdown
# Localization — Hyperlocal Research

Insurance is state- and region-specific. Before judging any quote's adequacy, pin down the user's
local context. **Research this live every run** (prefer the `research` plugin's `web-search` skill;
fall back to `WebSearch`) — never rely on baked-in state tables; minimums, catastrophe norms, and
carrier availability change year to year.

Use the current year in queries. Confirm figures against an authoritative source (a state
department-of-insurance page, III, NAIC, NerdWallet/Policygenius state guides).

## Dimensions to pin down

1. **State-mandated coverages & minimum limits**
   - Minimum liability limits (compare against the 100/300/100 floor — take the greater).
   - Is it a **no-fault / PIP** state? Is PIP or med-pay required, and at what limit?
   - Is **UM/UIM** mandatory, and any minimums?
   - Any other state-required coverage.
   - Example query: `"<state> minimum car insurance requirements <year> PIP uninsured motorist"`

2. **Catastrophe exposure & special deductibles** (home)
   - **Hurricane / windstorm / named-storm** percentage deductibles (common in coastal/Gulf/SE states).
   - **Flood** — excluded from home policies; is the property in a FEMA high-risk zone (needs NFIP or
     private flood)? Worth considering even in moderate zones.
   - **Wildfire** exposure and any related non-renewal / FAIR-plan dynamics.
   - **Earthquake** — excluded; separate policy where exposure exists.
   - **Sinkhole** and other region-specific perils.
   - Example queries: `"<state/metro> homeowners hurricane deductible <year>"`,
     `"<address or ZIP> FEMA flood zone"`, `"<state> wildfire insurance non-renewal <year>"`.

3. **Local rebuild cost per square foot**
   - Parameterizes the dwelling replacement-cost sanity check in the Home playbook.
   - Example query: `"<metro> home construction cost per square foot <year>"`.

4. **Carrier-availability dynamics**
   - Insurers non-renewing or exiting the state; **FAIR plan / residual market** as last resort.
   - Whether a cheap quote is from a carrier likely to raise rates or drop the market.
   - Example query: `"<state> home insurance market <year> insurers leaving non-renewal"`.

## Output — the "local context note"

Produce a short bulleted note that step 4 (adequacy) consumes, e.g.:

> **Local context — FL, 33xxx:** No-fault/PIP state ($10k PIP required); min liability 10/20/10 →
> well below the 100/300/100 floor, so use the floor. Expect a **separate hurricane % deductible**
> (2–5% of dwelling) and **wind coverage** scrutiny. **Flood excluded** — ZIP is Zone AE (high risk),
> NFIP/private flood effectively required. Rebuild cost ≈ $Xxx/sq-ft. Hard market: several carriers
> non-renewing; Citizens (FAIR plan) common — weigh carrier stability heavily.

Keep it to the facts that change a recommendation. If the user won't share a precise ZIP, work at the
state + metro level and say what's assumed.
````

- [ ] **Step 2: Sanity-check the four dimensions are present**

Run: `python -c "t=open('plugins/insurance/skills/coverage-review/reference/localization.md').read(); [t.index(s) for s in ['State-mandated','Catastrophe','rebuild cost','Carrier-availability','local context note']]; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add plugins/insurance/skills/coverage-review/reference/localization.md
git commit -m "feat(insurance): add hyperlocal localization reference"
```

---

## Task 5: `reference/carrier-quality.md` — carrier judgment + research handoff

**Files:**
- Create: `plugins/insurance/skills/coverage-review/reference/carrier-quality.md`

**Interfaces:**
- Consumes: referenced by `SKILL.md` step 5.
- Produces: the NAIC/AM Best method + the exact `research`-plugin handoff instruction.

- [ ] **Step 1: Write the carrier-quality reference**

Create the file with exactly this content:

````markdown
# Carrier Quality

Price is only half the decision — a cheap quote from a carrier that fights claims or is financially
weak is a bad deal. Weigh two objective signals plus live reputation.

## NAIC complaint index (claims-service reputation)

- The NAIC complaint index is normalized so **1.0 = the industry median** complaints per dollar of
  premium. **Below 1.0 = fewer complaints than average (good); above 1.0 = more (bad).**
- Look it up per carrier (NAIC Consumer Information Source, or NerdWallet/Policygenius carrier reviews
  that cite it) for the relevant line (home vs auto).
- Weight it heavily when two quotes are close on price/coverage.

## AM Best financial-strength rating (ability to pay claims)

- Measures the insurer's ability to pay claims. **A / A+ / A++ = strong; A- acceptable; B++ and below
  = scrutinize.** Also acceptable: comparable S&P / Moody's ratings.
- A materially cheaper quote from a sub-A- carrier is a flag, especially in a catastrophe-prone region
  where the insurer's balance sheet will be tested.

## Live reputation — hand off to the `research` plugin

For the specific carriers being compared (e.g. the incumbent vs a challenger), get anecdotal,
current reputation:

- Invoke the `research` plugin's **`literature-review`** skill with a query like
  `"<carrier> home insurance claims experience reviews <year>"` to pull Reddit/forum claims stories,
  and/or **`brand-check`** for a legitimacy/integrity read on an unfamiliar carrier.
- Fold the findings into the verdict as qualitative color (claims-handling reputation, rate-hike
  history, cancellation/non-renewal complaints) — not a hard score.

## Applying it in the verdict

- If a carrier wins on price but has a complaint index > 1.0, a sub-A- AM Best rating, or a pattern of
  claims complaints, **say so explicitly** and let the user weigh it.
- If the incumbent (e.g. Travelers) is being compared against a cheaper challenger, note the switching
  trade-off: potential savings vs claims-service and stability track record.
````

- [ ] **Step 2: Sanity-check key concepts are present**

Run: `python -c "t=open('plugins/insurance/skills/coverage-review/reference/carrier-quality.md').read(); [t.index(s) for s in ['NAIC complaint index','AM Best','literature-review','brand-check']]; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Full plugin validation now that all files exist**

Run: `claude plugin validate plugins/insurance && claude plugin validate .`
Expected: both pass. (If `claude` is unavailable, re-run the JSON-parse + SKILL frontmatter fallback checks from Tasks 1–2.)

- [ ] **Step 4: Commit**

```bash
git add plugins/insurance/skills/coverage-review/reference/carrier-quality.md
git commit -m "feat(insurance): add carrier-quality reference + research handoff"
```

---

## Task 6: Document the plugin in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (the "What this repository is" paragraph and the "Common commands" block)

**Interfaces:**
- Consumes: nothing. Documentation only.

- [ ] **Step 1: Update the repository description**

In `CLAUDE.md`, find the sentence in "## What this repository is" that says the marketplace
"currently hosts two plugins: `research` ... and `workout` ...". Change "two plugins" to "three
plugins" and append, after the workout description, one sentence:

```markdown
The `insurance` plugin (v0.1.0, 1 skill) is a stateless renewal helper: its `coverage-review` skill compares home/auto/umbrella/jewelry/life quotes apples-to-apples, judges coverage adequacy against the user's financial exposure and hyperlocal (state/region) factors, flags gaps (life, umbrella, disability), and weighs carrier claims reputation and financial strength — handing off to the `research` plugin for live carrier reputation. Prose + reference files only (no scripts, no stored PII).
```

- [ ] **Step 2: Add a validate line to Common commands**

In the "## Common commands" fenced block, next to the other `claude plugin validate` lines, add:

```bash
claude plugin validate plugins/insurance            # plugin
```

- [ ] **Step 3: Verify the edits landed**

Run: `python -c "t=open('CLAUDE.md').read(); assert 'three plugins' in t and 'coverage-review' in t and 'validate plugins/insurance' in t; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document insurance plugin in CLAUDE.md"
```

---

## Task 7: Manual dry-run verification

**Files:** none (verification only).

This is a manual smoke test — no automated tests exist for prose skills (consistent with the
`research` plugin). Do it once at the end.

- [ ] **Step 1: Confirm discovery**

Run: `claude plugin validate .`
Expected: passes, `insurance` listed among plugins. (Restart Claude Code / `/reload-plugins` in an
interactive session to pick up the new skill.)

- [ ] **Step 2: Trigger + walkthrough check (in an interactive session)**

Give the skill a realistic prompt (e.g. paste the user's Travelers home + auto declarations and ask
"review these and tell me if I have the right coverage — I'm in <state>"). Confirm the skill:
- runs the **localize** step for the user's state (state minimums, catastrophe/flood exposure),
- builds per-line **comparison tables** with unstated fields marked `not specified`,
- gives **adequacy verdicts** adjusted for local context and shows the sizing math,
- runs **gap analysis** flagging life, umbrella, and disability,
- weighs **carrier quality** and offers the research-plugin handoff,
- ends with a prioritized **action list** and the not-advice framing,
- writes **no files** unless asked.

- [ ] **Step 2 (fallback if not in an interactive session):** manually read `SKILL.md` and confirm all
  three reference files exist and are cited, and that each reference file's sanity-check from Tasks
  3–5 passed.

- [ ] **Step 3: Finalize the branch**

Use the `superpowers:finishing-a-development-branch` skill to choose how to integrate (merge / PR).

---

## Self-Review (completed by plan author)

**Spec coverage:** every spec section maps to a task — plugin/marketplace registration (Task 1),
7-step SKILL.md incl. profile/localize/intake/adequacy/carrier/gap/verdict (Task 2), coverage-playbook
with all six lines + localize hooks (Task 3), localization reference with the four dimensions (Task 4),
carrier-quality with NAIC/AM Best + research handoff (Task 5), CLAUDE.md docs (Task 6), and the manual
dry-run from the spec's testing section (Task 7). Non-goals honored via Global Constraints (no scripts,
stateless/no PII, live localization, not-advice framing).

**Placeholder scan:** no TBD/TODO; every file's full content is inline; verification steps show exact
commands and expected output.

**Type consistency:** file paths are consistent across tasks (`plugins/insurance/skills/coverage-review/...`);
the three reference filenames used in SKILL.md (Task 2) exactly match the files created in Tasks 3–5
(`coverage-playbook.md`, `localization.md`, `carrier-quality.md`); the `research` plugin skill names
(`web-search`, `literature-review`, `brand-check`) are used consistently.
