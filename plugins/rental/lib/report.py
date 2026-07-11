"""Render DealResult[] to a user-facing markdown report and a machine-readable CSV."""
from __future__ import annotations

import csv
import io

from lib.models import DealResult


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _money(x: float) -> str:
    return f"${x:,.0f}"


def render_markdown(results: list[DealResult], cfg: dict, rate_note: str) -> str:
    market = (cfg.get("market") or {}).get("label", "your market")
    lines = [f"# Rental shortlist — {market}", ""]
    lines.append(f"_Rate basis: {rate_note}. Ranked by cash-on-cash at asking price._")
    lines.append("")
    if not results:
        lines.append("No properties passed screening. Loosen thresholds or widen the search.")
        return "\n".join(lines)

    lines.append("| # | Address | Price | Rent/mo | Asking CoC | Cap rate | Max offer @ target |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        p = r.property
        asking = r.scenarios[0]
        mo = _money(r.max_offer_price) if r.max_offer_price is not None else "—"
        lines.append(
            f"| {i} | {p.address} | {_money(p.list_price)} | {_money(p.gross_monthly_rent or 0)}"
            f" | {_pct(asking.cash_on_cash)} | {_pct(asking.cap_rate)} | {mo} |"
        )
    lines.append("")

    for i, r in enumerate(results, 1):
        p = r.property
        lines.append(f"## {i}. {p.address}, {p.city} {p.zip}")
        lines.append("")
        lines.append(f"- List price: {_money(p.list_price)}")
        lines.append(f"- Estimated gross rent: {_money(p.gross_monthly_rent or 0)}/mo "
                     f"(source: {p.rent_source or 'n/a'})")
        if r.max_offer_price is not None:
            lines.append(f"- **Max offer to hit target: {_money(r.max_offer_price)}**")
        if p.url:
            lines.append(f"- Listing: {p.url}")
        lines.append("")
        lines.append("| Scenario | Price | Monthly P&I | NOI/yr | Cap rate | Cash flow/yr | Cash-on-Cash | Meets target |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for s in r.scenarios:
            lines.append(
                f"| {s.label} | {_money(s.price)} | {_money(s.monthly_pi)} | {_money(s.noi_annual)}"
                f" | {_pct(s.cap_rate)} | {_money(s.annual_cashflow)} | {_pct(s.cash_on_cash)}"
                f" | {'✅' if s.meets_target else '—'} |"
            )
        for note in r.notes:
            lines.append(f"> {note}")
        lines.append("")
    return "\n".join(lines)


def render_csv(results: list[DealResult]) -> str:
    buf = io.StringIO()
    cols = ["address", "city", "zip", "list_price", "gross_monthly_rent", "rent_source",
            "asking_cash_on_cash", "asking_cap_rate", "asking_monthly_cashflow",
            "max_offer_price", "url"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in results:
        p = r.property
        a = r.scenarios[0]
        w.writerow({
            "address": p.address, "city": p.city, "zip": p.zip,
            "list_price": f"{p.list_price:.0f}",
            "gross_monthly_rent": f"{(p.gross_monthly_rent or 0):.0f}",
            "rent_source": p.rent_source,
            "asking_cash_on_cash": f"{a.cash_on_cash:.4f}",
            "asking_cap_rate": f"{a.cap_rate:.4f}",
            "asking_monthly_cashflow": f"{a.annual_cashflow / 12:.0f}",
            "max_offer_price": "" if r.max_offer_price is None else f"{r.max_offer_price:.0f}",
            "url": p.url,
        })
    return buf.getvalue()
