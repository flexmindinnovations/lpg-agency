#!/usr/bin/env bash
# Everything CI runs, locally. If this passes, CI should pass.
#
# Deliberately the same commands CI invokes rather than a parallel
# implementation — a local check that diverges from CI is worse than none,
# because it produces false confidence.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "======================================================================"
echo " Repository checks"
echo "======================================================================"
echo "==> Design tokens are up to date"
node scripts/generate-tokens.mjs --check

echo "==> OpenAPI spec matches implementation"
(cd backend && uv run python scripts/export_openapi.py --check)

./scripts/lint.sh
./scripts/test.sh

echo
echo "======================================================================"
echo " All checks passed."
echo "======================================================================"
