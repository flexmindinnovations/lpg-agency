#!/usr/bin/env bash
# Run every test suite.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Backend (pytest)";  (cd backend  && uv run pytest -q)
echo "==> Frontend (jest)";   (cd frontend && npx nx run-many -t test --all)
echo "==> Mobile (flutter test)"
for dir in mobile/packages/* mobile/apps/*; do
  [[ -d "$dir/test" ]] && (cd "$dir" && flutter test) && echo "  OK $dir"
done
echo "All tests passed."
