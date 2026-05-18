#!/usr/bin/env bash
set -euo pipefail

cd /Users/zane/Downloads/aliyun_mcp

# 启动 MCP server（.env 由 python-dotenv 在应用内读取）
exec /Users/zane/Downloads/aliyun_mcp/.venv/bin/python main.py
