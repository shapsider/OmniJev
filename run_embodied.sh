#!/usr/bin/env bash
set -euo pipefail
OMNIJEV_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$OMNIJEV_ROOT"
if [ ! -x .venv-embodied/bin/python ]; then
  echo "先运行 ./setup_embodied.sh 安装仿真环境。" >&2
  exit 1
fi
export OMNIJEV_PROJECT_ROOT="$OMNIJEV_ROOT"
echo "OmniJev 具身实验台：http://127.0.0.1:${OMNIJEV_PORT:-8766}"
echo "Benchmark：http://127.0.0.1:${OMNIJEV_PORT:-8766}/benchmarks"
echo "默认规则演示不调用模型；选择 OmniJev 后连接本机 Bionic。"
exec .venv-embodied/bin/python -m embodied_jev.cli serve --port "${OMNIJEV_PORT:-8766}" --memory-only
