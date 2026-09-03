#!/usr/bin/env python3
"""Read a JSON list of rehab project specs on stdin, compute itemized cost
estimates using the NH Seacoast reference data, and print a markdown report.

Each project spec: {"project_type": str, "sqft": float, "tier": str|omit,
"quantity_overrides": dict|omit, "year_built": int|omit}.
"""
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from lib.rehab_cost import (
    estimate_project, total_rehab_cost, render_markdown,
    UnknownProjectTypeError, TierError, UnknownLineItemError,
)

REFERENCE_PATH = os.path.join(_PLUGIN_ROOT, "references", "rehab-costs-nh-seacoast.json")


def main() -> int:
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)

    specs = json.load(sys.stdin)
    estimates = []
    for spec in specs:
        try:
            estimates.append(estimate_project(
                project_type=spec["project_type"],
                sqft=spec["sqft"],
                reference=reference,
                tier=spec.get("tier"),
                quantity_overrides=spec.get("quantity_overrides"),
                year_built=spec.get("year_built"),
            ))
        except (UnknownProjectTypeError, TierError, UnknownLineItemError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        except (KeyError, TypeError) as e:
            print(f"error: malformed project spec {spec!r}: {e}", file=sys.stderr)
            return 2

    result = total_rehab_cost(estimates)
    print(render_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
