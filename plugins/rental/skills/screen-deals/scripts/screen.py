#!/usr/bin/env python3
"""Read Property[] JSON on stdin, screen with zero-API heuristics, write DealResult[] JSON."""
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib.config import load_merged, ConfigError
from lib.models import Property
from lib.rates import effective_rate
from lib.screen import screen


def main() -> int:
    try:
        cfg = load_merged()
    except FileNotFoundError:
        print("error: no config found — run /setup first", file=sys.stderr)
        return 3
    except ConfigError as e:
        print(f"error: invalid config: {e}", file=sys.stderr)
        return 3
    props = [Property.from_dict(d) for d in json.load(sys.stdin)]
    rate, note = effective_rate(cfg)
    results = screen(props, cfg, rate)
    print(json.dumps([r.to_dict() for r in results], ensure_ascii=False))
    print(f"screened {len(props)} -> {len(results)} passed ({note})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
