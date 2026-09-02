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
