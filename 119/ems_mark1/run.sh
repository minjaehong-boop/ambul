#!/usr/bin/env bash
# mark1 (Vector RAG) 런처:  ./run.sh server | cli
set -e
cd "$(dirname "$0")"
case "${1:-server}" in
  server) exec python -m ems_mark1.server ;;
  cli)    exec python -m ems_mark1.cli ;;
  *) echo "usage: $0 {server|cli}"; exit 1 ;;
esac
