#!/usr/bin/env bash
# EMS Commander(mark10) 실행 런처
#   ./run.sh server   → MCP 서버 (port 8080)
#   ./run.sh cli       → 대화형 클라이언트
#   ./run.sh http      → HTTP 데모 서버 (port 8090)
# 사전: vLLM 등 OpenAI 호환 LLM 서버가 떠 있어야 함 (README 참고)
set -e
cd "$(dirname "$0")"

CMD="${1:-server}"
case "$CMD" in
  server) exec python -m ems_commander.server ;;
  cli)    exec python -m ems_commander.cli ;;
  http)   exec python -m ems_commander.cli --http ;;
  *) echo "usage: $0 {server|cli|http}"; exit 1 ;;
esac
