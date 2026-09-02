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
