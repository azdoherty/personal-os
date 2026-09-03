"""Validation of user-supplied CLI tokens (constraint flags, equipment ids).

Every skill CLI takes comma-separated tokens from the user. A typo'd token
(`arm_load` instead of `arm-load`) must never silently degrade into "no
constraint" -- that would hand the user a program that ignores the injury it
was supposed to design around. These helpers turn a bad token into a loud,
actionable error instead.
"""
from __future__ import annotations

from model import CONSTRAINT_FLAGS, FOCUS_AREAS
import advisor


class TokenError(ValueError):
    """A user-supplied token was not in the legal set."""


def split_tokens(raw: str) -> list:
    """Split a comma-separated CLI value into stripped, non-empty tokens."""
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


def _check(tokens, legal, label: str) -> list:
    tokens = list(tokens)
    legal_sorted = sorted(legal)
    for token in tokens:
        if token not in legal:
            raise TokenError(
                f"unknown {label} {token!r}. Valid {label}s: {', '.join(legal_sorted)}"
            )
    return tokens


def validate_constraints(tokens) -> list:
    """Return the tokens unchanged, or raise TokenError naming the bad one."""
    return _check(tokens, set(CONSTRAINT_FLAGS), "constraint flag")


def validate_focus(tokens) -> list:
    """Return the tokens deduped (first occurrence wins, order preserved), or
    raise TokenError naming the bad one. `--focus core,core` is a typo, not a
    request for two identical core days -- left as-is it prints a program
    whose goal reads "split: core, core"."""
    return list(dict.fromkeys(_check(tokens, set(FOCUS_AREAS), "focus area")))


def equipment_ids(catalog=None) -> set:
    catalog = catalog if catalog is not None else advisor.load_equipment_catalog()
    return {item["equipment_id"] for item in catalog}


def validate_equipment(tokens, catalog=None) -> list:
    """Return the tokens unchanged, or raise TokenError naming the bad one."""
    return _check(tokens, equipment_ids(catalog), "equipment id")
