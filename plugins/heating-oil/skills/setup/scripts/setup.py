#!/usr/bin/env python3
"""Show or write the heating-oil config (lives in the OS config dir, never the repo).

  setup.py --show-path          # {"path": ..., "exists": bool}
  setup.py --show               # merged config (defaults + yours)
  echo '{"zip": "03801", ...}' | setup.py --write
"""
import argparse
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

from lib.config import (ConfigError, config_path, load_config, merge_defaults,
                        write_config)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--show-path", action="store_true")
    g.add_argument("--show", action="store_true")
    g.add_argument("--write", action="store_true", help="read config JSON on stdin")
    args = ap.parse_args()
    if args.show_path:
        p = config_path()
        print(json.dumps({"path": str(p), "exists": p.is_file()}))
    elif args.show:
        print(json.dumps(merge_defaults(load_config() or {}), indent=2))
    else:
        try:
            p = write_config(json.load(sys.stdin))
        except (ConfigError, json.JSONDecodeError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
