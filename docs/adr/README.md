# docs/adr/ — Pointer

**Architecture Decision Records do not live in this folder.**

They live in:

### → [`docs/architecture/15-architecture-decision-records.md`](../architecture/15-architecture-decision-records.md)

That document contains ADR-001 through ADR-026, in standard format (Status, Context, Decision, Consequences, Alternatives Considered), including the Phase 0 supersessions that moved the platform from the .NET architecture to Python/FastAPI/PostgreSQL.

---

## Why this folder looked populated but was not

`docs/adr/decisions.md` was a **byte-identical duplicate** of [`docs/business/decisions.md`](../business/decisions.md) — the *business* decisions log (D-01 … D-42, stakeholder-confirmed answers to the original open questions). It was never an architecture decision record, despite the folder name.

This was discovered during the Phase 0 repository assessment and corrected: `decisions.md` here is now a pointer stub, and the original content remains in full at its correct location.

## Which document do you want?

| You are looking for | Go to |
|---|---|
| Why we chose a technology or pattern (monorepo, PostgreSQL, WebSockets, Nx…) | [`docs/architecture/15-architecture-decision-records.md`](../architecture/15-architecture-decision-records.md) |
| What the business decided (cylinder types, order states, refund workflow, RBAC roles…) | [`docs/business/decisions.md`](../business/decisions.md) |
| Which original open questions were resolved, and by which decision | [`docs/engineering/open-questions.md`](../engineering/open-questions.md) |
| What was assumed before the business decided | [`docs/business/assumptions.md`](../business/assumptions.md) |
| Superseded .NET-era architecture documents | [`docs/architecture/superseded/`](../architecture/superseded/README.md) |

---

*Corrected during Phase 0 — Documentation Reconciliation, 2026-08-09.*
