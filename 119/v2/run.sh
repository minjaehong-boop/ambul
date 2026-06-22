#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Triage RAG (PageIndex edition) 실행 스크립트
#
# 사용법:
#   ./run.sh server [port]   — API 서버 (기본 8082)
#   ./run.sh ui     [port]   — Playground UI 서버만 실행 (기본 3000)
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

TYPE="${1:-server}"
PORT="${2:-}"


export APP_CONFIG_FILE="${APP_CONFIG_FILE:-$(pwd)/config.yaml}"

export PAGEINDEX_ROOT="${PAGEINDEX_ROOT:-$(pwd)/artifacts}"

case "$TYPE" in
  server)
    export EXAMPLE_TYPE=pageindex
    export PORT="${PORT:-8082}"
    echo "Starting TriagePageIndexChatbot on port $PORT ..."
    python server.py
    ;;
  ui)
    echo "Starting Playground UI on port ${PORT:-3000} ..."
    python playground/server.py "${PORT:-3000}"
    ;;
  *)
    echo "Usage: $0 {server|ui} [port]"
    exit 1
    ;;
esac
