#!/usr/bin/env bash
# 帧动画浏览器启动脚本（macOS / Linux）
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then echo "[x] 未找到 Python3"; exit 1; fi
exec "$PY" serve.py "$@"
