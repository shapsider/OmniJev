#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL_DIR="${OMNIJEV_MODEL_DIR:-$PWD/models/Nemotron-Omni-GGUF}"
SERVER="${OMNIJEV_LLAMA_SERVER:-$PWD/.cache/llama/build/bin/llama-server}"
MODEL="$MODEL_DIR/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-Q4_K_M.gguf"
PROJECTOR="$MODEL_DIR/mmproj-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16.gguf"
for file in "$MODEL" "$PROJECTOR"; do
  if [ ! -f "$file" ]; then echo "Missing model file: $file; Follow README to download." >&2; exit 1; fi
done
if [ ! -x "$SERVER" ]; then echo "Not found llama-server: $SERVER; Follow README to build, or set OMNIJEV_LLAMA_SERVER." >&2; exit 1; fi
# Optional per-process CUDA forward compatibility; never alters the system driver.
if [ -n "${OMNIJEV_CUDA_COMPAT:-}" ]; then
  export LD_LIBRARY_PATH="$OMNIJEV_CUDA_COMPAT${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
export LD_LIBRARY_PATH="$(dirname "$SERVER")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p .cache/cuda
export CUDA_CACHE_PATH="${CUDA_CACHE_PATH:-$PWD/.cache/cuda}"
exec "$SERVER" -m "$MODEL" --mmproj "$PROJECTOR" \
  --alias "${OMNIJEV_MODEL:-omnijev-nemotron}" \
  --host 127.0.0.1 --port "${OMNIJEV_BACKEND_PORT:-1234}" \
  -ngl 99 -c "${OMNIJEV_CONTEXT:-8192}" --parallel 1 --jinja --fit off "$@"
