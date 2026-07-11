"""Zero-API screening: estimate rent from config heuristics, underwrite, filter by
thresholds, and rank. Runs BEFORE any RentCast call so the user can prune the list.
"""
from __future__ import annotations

from lib.models import Property, DealResult
from lib.underwrite import build_scenarios, compute_returns


def heuristic_rent(prop: Property, screening: dict) -> tuple[float | None, str]:
    mode = screening.get("heuristic_rent_mode", "per_sqft")
    if mode == "per_sqft":
        if prop.sqft:
            return prop.sqft * screening["rent_per_sqft"], "heuristic:per_sqft"
        return None, "heuristic:per_sqft (no sqft)"
    if mode == "per_bedroom":
        table = screening.get("rent_per_bedroom", {})
        if prop.beds is not None and table:
            max_key = max(int(k) for k in table)
            key = str(min(int(prop.beds), max_key))
            return float(table[key]), "heuristic:per_bedroom"
        return None, "heuristic:per_bedroom (no beds)"
    return None, f"heuristic:unknown-mode({mode})"


def passes_thresholds(returns: dict, gross_rent: float, price: float,
                      thresholds: dict) -> bool:
    if returns["cash_on_cash"] < thresholds["target_coc_pct"]:
        return False
    if returns["annual_cashflow"] / 12.0 < thresholds["min_monthly_cashflow"]:
        return False
    if thresholds.get("use_one_percent_rule") and price and gross_rent < 0.01 * price:
        return False
    return True


def screen(props: list[Property], cfg: dict, effective_rate: float) -> list[DealResult]:
    results: list[DealResult] = []
    for prop in props:
        rent, source = heuristic_rent(prop, cfg["screening"])
        if rent is None or not prop.list_price:
            continue
        prop.gross_monthly_rent = rent
        prop.rent_source = source
        asking = compute_returns(prop, cfg, prop.list_price, effective_rate)
        if not passes_thresholds(asking, rent, prop.list_price, cfg["thresholds"]):
            continue
        scenarios, max_price = build_scenarios(prop, cfg, effective_rate)
        results.append(DealResult(
            property=prop, scenarios=scenarios, max_offer_price=max_price,
            effective_rate=effective_rate, rank_metric=asking["cash_on_cash"],
            notes=[f"rent estimated by {source}"],
        ))
    results.sort(key=lambda r: r.rank_metric, reverse=True)
    return results
