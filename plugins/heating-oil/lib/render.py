"""Markdown rendering of ranked dealer results."""
from __future__ import annotations


def _money(x) -> str:
    return f"${x:,.2f}" if isinstance(x, (int, float)) else "—"


def _age(e) -> str:
    a = e.get("age_days")
    return "unknown" if a is None else ("today" if a == 0 else f"{a}d ago")


def render_markdown(result: dict, gallons: float, zip_code: str = "",
                    benchmark: float | None = None, show_excluded: int = 5) -> str:
    ranked, excluded = result["ranked"], result["excluded"]
    where = f" near {zip_code}" if zip_code else ""
    lines = [f"# Heating oil prices{where} — {gallons:g} gal", ""]
    if benchmark:
        lines.append(f"State average benchmark: **${benchmark:.3f}/gal** "
                     f"({_money(benchmark * gallons)} for {gallons:g} gal)")
        lines.append("")
    if not ranked:
        lines.append("_No dealer passed the filters. See excluded dealers below; "
                     "consider lowering `--min-score` or researching inconclusive dealers._")
    else:
        best = ranked[0]
        lines.append(f"**Best: {best['dealer']}** ({best.get('town') or '?'}) — "
                     f"${best['price_per_gal']:.3f}/gal, {_money(best['total'])} total, "
                     f"reputation {best['reputation']['score']:g}"
                     + (f" — call {best['phone']}" if best.get("phone") else ""))
        if benchmark:
            diff = benchmark - best["price_per_gal"]
            lines.append(f"That's ${abs(diff):.3f}/gal {'below' if diff >= 0 else 'above'} the benchmark.")
        lines += ["", "| # | Dealer | Town | Phone | $/gal (tier) | Total | Reputation | Updated | Sources |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for i, e in enumerate(ranked, 1):
            rep = e.get("reputation") or {}
            rep_txt = f"{rep.get('score', 0):g} {rep.get('verdict', '')}"
            if e.get("allowlisted"):
                rep_txt += " (allowlisted)"
            elif not rep.get("researched"):
                rep_txt += " (unresearched)"
            name = f"[{e['dealer']}]({e['url']})" if e.get("url") else e["dealer"]
            fee = f" +{_money(e['fee'])} fee" if e.get("fee") else ""
            lines.append(f"| {i} | {name} | {e.get('town', '')} | {e.get('phone', '')} | "
                         f"${e['price_per_gal']:.3f} ({e['tier']}+){fee} | {_money(e['total'])} | "
                         f"{rep_txt} | {_age(e)} | {', '.join(e.get('sources', []))} |")
    if excluded and show_excluded:
        lines += ["", "## Cheaper or notable dealers excluded", ""]
        for e in excluded[:show_excluded]:
            price = f"${e['price_per_gal']:.3f}/gal" if e.get("price_per_gal") else "n/a"
            lines.append(f"- {e['dealer']} ({e.get('town') or '?'}) — {price}: {e['excluded_reason']}")
    lines += ["", "_Prices are as listed by the source sites; confirm price, fees, "
              "and payment terms (COD cash/check/card) when you call._"]
    return "\n".join(lines) + "\n"
