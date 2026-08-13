#!/bin/sh
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then PYTHON=python3; elif command -v python >/dev/null 2>&1; then PYTHON=python; else echo "Python 3 is required. Install it from the official operating system source and run again."; exit 3; fi
exec "$PYTHON" "$BASE/portable.py" bootstrap "$@"
