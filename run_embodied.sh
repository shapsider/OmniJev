#!/usr/bin/env bash
set -euo pipefail
OMNIJEV_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$OMNIJEV_ROOT"
if [ ! -x .venv-embodied/bin/python ]; then
  echo "Run ./setup_embodied.sh first to install the simulation environment." >&2
  exit 1
fi
export OMNIJEV_PROJECT_ROOT="$OMNIJEV_ROOT"
echo "OmniJev Embodied workbench: http://127.0.0.1:${OMNIJEV_PORT:-8766}"
echo "Benchmark: http://127.0.0.1:${OMNIJEV_PORT:-8766}/benchmarks"
echo "The default rule demo does not call a model; OmniJev policies connect to the compatible inference backend specified by OMNIJEV_BASE_URL."
exec .venv-embodied/bin/python -m embodied_jev.cli serve --port "${OMNIJEV_PORT:-8766}" --memory-only
