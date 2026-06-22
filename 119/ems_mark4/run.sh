#!/usr/bin/env bash
# mark4 (Direct Access, 병원 DB 없음) 런처:  ./run.sh server | cli
set -e
cd "$(dirname "$0")"
case "${1:-server}" in
  server) exec python -m ems_mark4.server ;;
  cli)    exec python -m ems_mark4.cli ;;
  *) echo "usage: $0 {server|cli}"; exit 1 ;;
esac
