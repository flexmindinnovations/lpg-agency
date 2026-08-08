#!/usr/bin/env bash
# Lint and type-check every stack. Read-only: never modifies files.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Backend: ruff check";      (cd backend && uv run ruff check .)
echo "==> Backend: ruff format";     (cd backend && uv run ruff format --check .)
echo "==> Backend: mypy --strict";   (cd backend && uv run mypy)
echo "==> Backend: import-linter";   (cd backend && uv run lint-imports)
echo "==> Frontend: eslint";         (cd frontend && npx nx run-many -t lint --all)
echo "==> Mobile: dart analyze"
for dir in mobile/packages/* mobile/apps/*; do
  [[ -f "$dir/pubspec.yaml" ]] && (cd "$dir" && flutter analyze --no-fatal-warnings >/dev/null) && echo "  OK $dir"
done
echo "All lint checks passed."
