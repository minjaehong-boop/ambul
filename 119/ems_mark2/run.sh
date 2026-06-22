#!/usr/bin/env bash
# mark2 (Long-Context) 런처:  ./run.sh server | cli
set -e
cd "$(dirname "$0")"
case "${1:-server}" in
  server) exec python -m ems_mark2.server ;;
  cli)    exec python -m ems_mark2.cli ;;
  *) echo "usage: $0 {server|cli}"; exit 1 ;;
esac
