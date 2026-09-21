#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
OMNIJEV_PYTHON="${OMNIJEV_PYTHON:-}"
if [ -z "$OMNIJEV_PYTHON" ]; then
  for candidate in python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys;sys.exit(sys.version_info < (3,12))'; then
      OMNIJEV_PYTHON="$candidate"; break
    fi
  done
fi
if [ -z "$OMNIJEV_PYTHON" ]; then
  echo "Python 3.12+ is required. Set OMNIJEV_PYTHON=/path/to/python3 and run again." >&2; exit 1
fi
# Keep installation scratch files on the project volume (useful on containers).
mkdir -p .cache/tmp
export TMPDIR="${TMPDIR:-$PWD/.cache/tmp}"
export PIP_NO_CACHE_DIR="${PIP_NO_CACHE_DIR:-1}"
"$OMNIJEV_PYTHON" -m venv .venv-embodied
.venv-embodied/bin/python -m pip install --no-compile -r embodied/requirements.lock
.venv-embodied/bin/python -m pip install --no-compile --no-deps -e . -e ./embodied
echo "Installation complete. Frontend build artifacts are included. See README for model download and backend startup; start the workbench with ./run_embodied.sh."
