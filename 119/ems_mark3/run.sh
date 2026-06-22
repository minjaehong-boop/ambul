#!/usr/bin/env bash
# mark3 (Direct Access) 런처:  ./run.sh server | cli
set -e
cd "$(dirname "$0")"
case "${1:-server}" in
  server) exec python -m ems_mark3.server ;;
  cli)    exec python -m ems_mark3.cli ;;
  *) echo "usage: $0 {server|cli}"; exit 1 ;;
esac
