#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${MCP_HOST:-0.0.0.0}"
PORT="${MCP_PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-$SCRIPT_DIR/.venv/bin/python}"

exec "$PYTHON_BIN" main.py --transport http --host "$HOST" --port "$PORT"
