#!/usr/bin/env python3
"""Persist rental plugin config. Claude gathers answers (per SKILL.md) and pipes a
JSON object of user values to `--write`; this script merges defaults, validates, and
saves to the OS config dir. No secrets are echoed."""
import argparse
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.config import config_path, merge_defaults, validate


def main() -> int:
    ap = argparse.ArgumentParser(description="Write validated rental config")
    ap.add_argument("--write", action="store_true", help="Read user JSON on stdin and save")
    ap.add_argument("--show-path", action="store_true")
    args = ap.parse_args()

    path = config_path()
    if args.show_path:
        print(json.dumps({"path": str(path), "exists": path.is_file()}))
        return 0
    if args.write:
        user = json.load(sys.stdin)
        merged = merge_defaults(user)
        errors = validate(merged)
        if errors:
            print("error: " + "; ".join(errors), file=sys.stderr)
            return 2
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        print(f"wrote config to {path}", file=sys.stderr)
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
