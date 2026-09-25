#!/usr/bin/env bash
# Pull the latest code, rebuild images, migrate, and (re)start the stack.
# Safe to re-run; it is the whole update procedure.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "Missing .env - run ./generate-env.sh first." >&2; exit 1; }

if [ "${SKIP_PULL:-0}" != "1" ]; then
  git -C ../.. pull --ff-only
fi

compose=(docker compose -f docker-compose.prod.yml)

"${compose[@]}" build backend web
"${compose[@]}" up -d --remove-orphans
"${compose[@]}" ps

docker image prune -f >/dev/null
