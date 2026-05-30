#!/usr/bin/env bash
# reddit-search: thin shell wrapper around the Python implementation.
# See search.py for full options. Args passed through verbatim.
exec python3 "$(dirname "$0")/search.py" "$@"
