#!/usr/bin/env bash
# Format every stack.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Backend (ruff)";   (cd backend  && uv run ruff format . && uv run ruff check --fix .)
echo "==> Frontend (prettier)"; (cd frontend && npx prettier --write . >/dev/null && echo "  formatted")
echo "==> Mobile (dart format)"
for dir in mobile/packages/* mobile/apps/*; do
  [[ -f "$dir/pubspec.yaml" ]] && (cd "$dir" && dart format . >/dev/null) && echo "  $dir"
done
