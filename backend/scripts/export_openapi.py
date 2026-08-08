"""Export the generated OpenAPI specification (ADR-026).

The workflow is **code-first generation, contract-first consumption**:

1. Pydantic models and route metadata are the single source of truth.
2. FastAPI generates the spec; this script writes it to
   ``backend/openapi/openapi.json``, which **is committed**.
3. All three clients generate typed clients from that committed artifact —
   never from a running server, never by hand.
4. ``--check`` fails when the committed file differs from freshly generated
   output, so the contract cannot silently drift from the implementation.

Step 4 is the load-bearing one. It converts "keep the spec up to date" from a
discipline into a build failure, and it makes every contract change visible in
a pull-request diff, which is what "the API contract is part of the public
interface" has to mean operationally.

Usage:
    python scripts/export_openapi.py            # write
    python scripts/export_openapi.py --check    # verify, exit 1 on drift
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lpg.api.app import create_app
from lpg.config.settings import Settings

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "openapi" / "openapi.json"


def generate_spec() -> str:
    """Return the OpenAPI document as formatted JSON."""
    app = create_app(Settings(environment="local", docs_enabled=True))
    spec = app.openapi()
    # sort_keys makes the output deterministic, so a diff shows genuine
    # contract changes rather than dictionary ordering noise.
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed spec matches generated output; do not write.",
    )
    args = parser.parse_args()

    generated = generate_spec()

    if args.check:
        if not OUTPUT_PATH.exists():
            print(f"FAIL: {OUTPUT_PATH} does not exist. Run without --check.", file=sys.stderr)
            return 1
        committed = OUTPUT_PATH.read_text(encoding="utf-8")
        if committed != generated:
            print(
                "FAIL: the committed OpenAPI spec is out of date.\n"
                "      The API contract has changed but the artifact was not regenerated.\n"
                "      Run: python scripts/export_openapi.py",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {OUTPUT_PATH.name} matches generated output.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(generated, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
