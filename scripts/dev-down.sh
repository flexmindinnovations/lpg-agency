#!/usr/bin/env bash
# Stop the local development environment. Pass --volumes to also delete data.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--volumes" ]]; then
  echo "Stopping and DELETING all local data..."
  docker compose -f infrastructure/docker/docker-compose.yml down -v
else
  docker compose -f infrastructure/docker/docker-compose.yml down
fi
