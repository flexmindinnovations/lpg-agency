#!/usr/bin/env python3
"""Guard against superseded-architecture instructions reappearing.

Phase 0 moved the platform from ASP.NET Core / EF Core / MediatR / Azure SQL /
SignalR to Python / FastAPI / SQLAlchemy / PostgreSQL, and Phase 1's follow-up
named Supabase as the managed PostgreSQL host. The superseded documents were
**preserved, not deleted**, so the decision history stays traceable.

That preservation creates a specific hazard this script exists to prevent: an
agent or engineer encountering .NET guidance and treating it as current. A
one-time cleanup does not hold — the next person to copy a paragraph from
`superseded/` reintroduces it silently.

The distinction that matters:

  FORBIDDEN   "Use EF Core global query filters for tenant isolation."
              An instruction. Someone could follow it.

  ALLOWED     "EF Core global query filters were superseded by PostgreSQL RLS."
              A historical record. Following it is impossible.

So this checks for obsolete technology *named as current guidance*, and treats
a line as historical when it carries an explicit marker. Run it in CI, not just
once.

Usage:
    python scripts/check_architecture_consistency.py
    python scripts/check_architecture_consistency.py --verbose
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode the arrows used
# below. Reconfiguring here keeps the script runnable in a plain terminal as
# well as in CI, without ASCII-ing the output everywhere.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent

# Paths exempt from the check, each for a stated reason.
EXEMPT_PREFIXES = (
    # The preserved .NET architecture. Its whole purpose is to contain this.
    "docs/architecture/superseded/",
    # The record of the reconciliation itself: task lists and plans that name
    # what was replaced. Editing these to satisfy the checker would destroy
    # the audit trail of the work.
    "planning/features/00-documentation-reconciliation/",
    # This file.
    "scripts/check_architecture_consistency.py",
)

# Superseded technologies, matched as whole words so "Razorpay" does not trip
# on "Razor" and ".NET" does not trip on "ASP.NETWORK".
FORBIDDEN_PATTERNS: dict[str, str] = {
    r"\bASP\.NET\b": "ASP.NET Core → FastAPI (ADR-012)",
    r"(?<![\w.])\.NET\b(?!\s*(?:architecture|design|stack|era|direction|version))": (
        ".NET → Python 3.13 (ADR-012)"
    ),
    r"\bEF Core\b": "EF Core → SQLAlchemy 2.x (ADR-012)",
    r"\bEntity Framework\b": "Entity Framework → SQLAlchemy 2.x (ADR-012)",
    r"\bMediatR\b": "MediatR → application services (ADR-014)",
    r"\bAzure SQL\b": "Azure SQL → PostgreSQL on Supabase (ADR-013, ADR-027)",
    r"\bSQL Server\b": "SQL Server → PostgreSQL (ADR-013)",
    r"\bSignalR\b": "SignalR → FastAPI WebSockets + Redis Pub/Sub (ADR-015)",
    r"\bQuestPDF\b": "QuestPDF → Python PDF renderer (ADR-016)",
    r"\bZXing(?:\.Net)?\b": "ZXing.Net → python-barcode / qrcode (ADR-016)",
    r"\bQRCoder\b": "QRCoder → qrcode (ADR-016)",
    r"\bNetArchTest\b": "NetArchTest → import-linter (ADR-024)",
    r"\bFluentValidation\b": "FluentValidation → Pydantic v2 (ADR-012)",
    r"\bSerilog\b": "Serilog → structlog (ADR-012)",
    r"\bHangfire\b": "Hangfire → background worker (ADR-023)",
    r"\bSwashbuckle\b|\bNSwag\b": "Swashbuckle/NSwag → FastAPI OpenAPI (ADR-026)",
    r"\bAsNoTracking\b": "AsNoTracking() → SQLAlchemy read patterns",
    r"\bAsp\.Versioning\b": "Asp.Versioning → FastAPI router prefix (ADR-009)",
    r"\bDbContext\b": "DbContext → SQLAlchemy session (ADR-012)",
    r"\.csproj\b|\.sln\b": ".NET project files — none exist in this repository",
    r"\bC#\b": "C# → Python (ADR-012)",
}

# A line carrying one of these is a historical record, not an instruction.
# Deliberately explicit: an author who wants an exemption must say why in the
# line itself, which is exactly the documentation we want anyway.
HISTORICAL_MARKERS = (
    "supersede",
    "superseded",
    "superseding",
    "historical",
    "no longer",
    "not adopted",
    "not applicable",
    "originally",
    "original direction",
    "rejected",
    "replaced by",
    "was replaced",
    "rebound",
    "amended",
    "amendment",
    "preserved",
    "do not implement",
    "never implemented",
    "phase 0",
    "legacy",
    "would have",
    "instead of",
    "rather than",
    "equivalent of",
    "→",
    "->",
    "corrected",
    "previously",
    "earlier",
    "deprecat",
    "carried forward",
    "replacement",
    "this script",
    "forbidden_patterns",
)

# Naming a current-stack technology in the same line as a superseded one means
# the line is comparing or translating between them — "PostgreSQL has no
# clustered index like SQL Server", "PostgreSQL over Azure SQL". Those are
# useful engineering context, not instructions to use the old thing.
CURRENT_STACK_TERMS = (
    "postgresql",
    "fastapi",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "python",
    "supabase",
    "structlog",
    "import-linter",
    "redis pub/sub",
    "websocket",
    "application service",
)


def mentions_current_stack(line: str) -> bool:
    lowered = line.lower()
    return any(term in lowered for term in CURRENT_STACK_TERMS)


# A line citing an ADR is discussing a decision, not issuing an instruction.
# "ADR-004 chose CQRS via MediatR" records what was decided; it does not tell
# anyone to install MediatR.
_ADR_CITATION = re.compile(r"\bADR-\d{3}\b|\bD-\d{2}\b")


def cites_a_decision(line: str) -> bool:
    return bool(_ADR_CITATION.search(line))


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=REPO_ROOT, check=True
    )
    return [f for f in result.stdout.splitlines() if f.strip()]


def is_exempt(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def is_historical(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in HISTORICAL_MARKERS)


# A superseded ADR keeps its original text verbatim — that is the point of the
# register. Detecting the section boundary is more precise than exempting the
# whole file, which would let a genuinely new .NET instruction hide there.
_ADR_HEADING = re.compile(r"^#{2,3}\s+ADR-\d+", re.IGNORECASE)
# Both superseded and amended ADRs keep their original Decision text verbatim,
# per this register's own stated Format policy. An amendment note above the
# original explains what changed.
_SUPERSEDED_MARK = re.compile(r"superseded|amended", re.IGNORECASE)


def superseded_line_numbers(content: str) -> set[int]:
    """Line numbers belonging to an ADR section marked Superseded."""
    lines = content.splitlines()
    superseded: set[int] = set()

    section_starts = [i for i, line in enumerate(lines) if _ADR_HEADING.match(line)]
    for index, start in enumerate(section_starts):
        end = section_starts[index + 1] if index + 1 < len(section_starts) else len(lines)
        # An ADR is superseded when its status block says so — always within a
        # few lines of the heading.
        header = "\n".join(lines[start : min(start + 12, end)])
        if _SUPERSEDED_MARK.search(header):
            superseded.update(range(start + 1, end + 1))  # 1-indexed
    return superseded


CHECKED_SUFFIXES = {
    ".md", ".yml", ".yaml", ".json", ".txt", ".py", ".ts", ".tsx",
    ".dart", ".html", ".css", ".toml", ".sql", ".ini", ".mjs", ".cfg",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="List every file scanned.")
    args = parser.parse_args()

    compiled = [(re.compile(p, re.IGNORECASE), reason) for p, reason in FORBIDDEN_PATTERNS.items()]
    violations: list[tuple[str, int, str, str]] = []
    scanned = 0

    for rel_path in tracked_files():
        if is_exempt(rel_path):
            continue
        path = REPO_ROOT / rel_path
        if path.suffix.lower() not in CHECKED_SUFFIXES or not path.is_file():
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        scanned += 1
        if args.verbose:
            print(f"  scanned {rel_path}")

        exempt_lines = (
            superseded_line_numbers(content) if rel_path.endswith(".md") else set()
        )

        for lineno, line in enumerate(content.splitlines(), start=1):
            if lineno in exempt_lines:
                continue
            if is_historical(line) or mentions_current_stack(line) or cites_a_decision(line):
                continue
            for pattern, reason in compiled:
                if pattern.search(line):
                    violations.append((rel_path, lineno, line.strip()[:110], reason))
                    break

    print(f"Scanned {scanned} tracked files for superseded-architecture instructions.")

    if violations:
        print(f"\nFOUND {len(violations)} probable instruction(s) referencing superseded technology:\n")
        for rel_path, lineno, snippet, reason in violations:
            print(f"  {rel_path}:{lineno}")
            print(f"    {snippet}")
            print(f"    → {reason}\n")
        print(
            "Each line above reads as current guidance. Either translate it to the\n"
            "Python/FastAPI equivalent, or — if it is genuinely a historical note —\n"
            "state that explicitly in the line (e.g. 'superseded by', 'no longer')."
        )
        return 1

    print("OK: no superseded-architecture instructions on active paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
