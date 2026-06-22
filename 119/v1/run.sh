#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Triage RAG v1 — NVIDIA GenerativeAIExamples framework slice 런처
#
# chain_server/server.py 는 cwd 기준 상대경로(RAG/examples/...)로 예제를
# 로드하므로, 반드시 v1 디렉터리를 cwd 로 고정한 뒤 uvicorn 을 띄운다.
#
# 사용법:
#   ./run.sh                 # 기본 포트 8081
#   ./run.sh 9000            # 포트 지정
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

PORT="${1:-${PORT:-8081}}"

# 이 슬라이스는 advanced_rag/triage_rag 예제 하나만 포함한다.
export EXAMPLE_PATH="${EXAMPLE_PATH:-advanced_rag/triage_rag}"
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

echo "Starting Triage RAG (NVIDIA framework slice) on port $PORT ..."
echo "  EXAMPLE_PATH=$EXAMPLE_PATH"
echo "  cwd=$(pwd)"

exec python -m uvicorn RAG.src.chain_server.server:app \
  --host 0.0.0.0 \
  --port "$PORT"
