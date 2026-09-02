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
