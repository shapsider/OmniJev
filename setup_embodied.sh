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
  echo "需要 Python 3.12+。可设置 OMNIJEV_PYTHON=/path/to/python3 再运行。" >&2; exit 1
fi
"$OMNIJEV_PYTHON" -m venv .venv-embodied
.venv-embodied/bin/python -m pip install -r embodied/requirements.lock
.venv-embodied/bin/python -m pip install --no-deps -e . -e ./embodied
echo "安装完成。前端构建产物已包含。模型权重需从后端官方页面单独下载并由后端加载；然后运行 ./run_embodied.sh。"
