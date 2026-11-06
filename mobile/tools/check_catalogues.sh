#!/usr/bin/env bash
# Checks every typed string catalogue (story 2.1):
#   1. the committed generated Dart matches its JSON (regenerate, expect no diff);
#   2. no translation file has a key English does not have (the generator drops
#      such keys silently, so a typo would never show);
#   3. lists keys still missing from a translation (informational: English is
#      shown for them).
# Run from anywhere: tools/check_catalogues.sh
set -euo pipefail
cd "$(dirname "$0")/.."

status=0
for dir in packages/design_system apps/admin_app apps/customer_app apps/driver_app; do
  echo "== $dir"
  before="$(mktemp -d)"
  cp -R "$dir/lib/src/i18n/." "$before/"
  (cd "$dir" && flutter pub get >/dev/null && dart run slang >/dev/null)
  if ! diff -r -q "$before" "$dir/lib/src/i18n" >/dev/null; then
    echo "  generated catalogue is out of date: run 'dart run slang' in $dir and commit"
    diff -r -q "$before" "$dir/lib/src/i18n" || true
    status=1
  fi
  out="$(mktemp -d)"
  (cd "$dir" && dart run slang analyze --outdir="$out" >/dev/null)
  if python3 - "$out/_unused_translations.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
def leaves(n): return sum(leaves(v) if isinstance(v, dict) else 1 for v in n.values())
extra = {k: v for k, v in data.items() if not k.startswith("@@") and leaves(v)}
if extra:
    print("  keys in a translation that English does not have:")
    print("  " + json.dumps(extra, ensure_ascii=False))
    sys.exit(1)
PY
  then :; else status=1; fi
  python3 - "$out/_missing_translations.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
for lang, keys in ((k, v) for k, v in data.items() if not k.startswith("@@")):
    def count(n): return sum(count(v) if isinstance(v, dict) else 1 for v in n.values())
    print(f"  note: {lang} is missing {count(keys)} key(s); English is shown for them")
PY
done
exit $status
