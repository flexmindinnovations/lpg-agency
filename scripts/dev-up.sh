#!/usr/bin/env bash
# Start the local development environment (PostgreSQL + Redis + MinIO).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Starting PostgreSQL, Redis, and MinIO..."
docker compose -f infrastructure/docker/docker-compose.yml up -d

echo "Waiting for health checks..."
for _ in $(seq 1 30); do
  if docker compose -f infrastructure/docker/docker-compose.yml ps --format json 2>/dev/null | grep -q '"Health":"healthy"'; then
    break
  fi
  sleep 2
done

docker compose -f infrastructure/docker/docker-compose.yml ps
echo
echo "PostgreSQL : localhost:${POSTGRES_PORT:-55432}  (databases: lpg_dev, lpg_test)"
echo "Redis      : localhost:${REDIS_PORT:-56379}"
echo "MinIO      : localhost:${MINIO_API_PORT:-59000}  (console: localhost:${MINIO_CONSOLE_PORT:-59001})"
