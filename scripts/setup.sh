#!/usr/bin/env bash
# One-time developer setup.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Checking prerequisites"
missing=0
for tool in python uv node npm flutter docker git; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '  %-8s %s\n' "$tool" "$($tool --version 2>&1 | head -1)"
  else
    printf '  %-8s MISSING\n' "$tool"
    missing=1
  fi
done
[[ $missing -eq 1 ]] && { echo "Install the missing tools, then re-run."; exit 1; }

echo
echo "==> Environment file"
[[ -f .env ]] && echo "  .env already exists, leaving it alone" || { cp .env.example .env; echo "  created .env from .env.example"; }

echo
echo "==> Backend dependencies"
(cd backend && uv sync)

echo
echo "==> Frontend dependencies"
(cd frontend && npm ci --prefer-offline --no-audit || npm install)

echo
echo "==> Mobile dependencies"
for dir in mobile/packages/* mobile/apps/*; do
  [[ -f "$dir/pubspec.yaml" ]] && (cd "$dir" && flutter pub get >/dev/null) && echo "  $dir"
done

echo
echo "==> Design tokens"
node scripts/generate-tokens.mjs

echo
echo "Setup complete. Start the database with: ./scripts/dev-up.sh"
