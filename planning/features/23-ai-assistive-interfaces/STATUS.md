# AI Assistive Interfaces — Status

## Current Status

- **State:** 🔵 **NOT STARTED** — `PLAN.md`'s own scope (complaint auto-triage, KYC document extraction, conversational ordering, voice capture for field staff, an analytics copilot, an MDG risk copilot, delivery photo verification) is still planned only, not built. One narrower slice — a fixed-tool-menu precursor to the analytics copilot (A12) — was pulled forward and built independently, sharing its substrate with Phase 21's own Model Gateway; see the Exception section below. This does not move `State` off NOT STARTED, since it is a narrower, safer precursor to one slice (A12) out of this phase's much larger backlog (A5–A8, A11, A13 all remain untouched).
- **Created:** 2026-08-18

## Exception: AI Command Center (A12 Precursor) — 🟢 DONE

`PLAN.md`'s Slice E, "Internal analytics copilot" (research row A12 — text-to-SQL over a curated semantic layer, `tenant_id` enforced by RLS at the DB session, refuse rather than guess on ambiguous metrics), was not built as specified. Instead, a **narrower, safer precursor** was built and pulled forward: instead of letting the model generate SQL against a semantic layer, it picks from a **fixed menu of vetted, pre-built read-only tools** — removing SQL-generation/injection risk entirely at the cost of being less open-ended. This is honestly *not* A12 — it answers only what its three tools can answer, not arbitrary operational questions — but it proves the same core capability (a staff-facing natural-language operations assistant, tenant-isolated, backend-enforced authorization) with materially less risk, and is the substrate A12 itself (or a future tool-registry expansion) would build on. See ADR-045 for the full design; see `21-ai-foundation/STATUS.md`'s own "Exception: Model Gateway" section for the complete commit-by-commit build breakdown (the same 5 commits, `6fd078d`→`aba1698`, deliver both this phase's exception and Phase 21's own substrate — they are the same slice, viewed from two phases' backlogs).

Highlights not repeated in full here (see `21-ai-foundation/STATUS.md` for the complete list):

- **The rule this phase's own `PLAN.md` is built around held**: the model never decided anything that carries money, entitlement, or compliance weight — every one of the three tools is a pure read, and no tool can mutate any record. Per-tool `required_permission` filtering (`orders:read`, `inventory:read`, `complaints.manage`) is the real safety boundary — a hallucinated or out-of-grant tool call is rejected before it ever executes, never trusted to the model's own restraint.
- **Live-verified with a real Gemini API key**, not mocked: the model correctly reasoned across all three tools in a single request when a question warranted it (`get_today_delivery_status`, `get_inventory_overview`, `get_open_complaints_summary`), producing an answer that named the actual operational signal (9 stale `out_for_delivery` orders) as the likely delay cause and cross-referenced open complaints and inventory as supporting context — genuine multi-tool reasoning, not a scripted response.
- **Tenant isolation** is enforced the same way as everywhere else in this codebase — RLS at the database session via the existing request-scoped `UnitOfWork`, never a filter the model could omit or the application layer could forget. No dedicated cross-tenant-leakage test was written for this slice specifically (unlike A12's own stated verification requirement) because no tool accepts a caller-supplied identifier that could reference another tenant's data at all — every tool is zero-argument, reading only the calling principal's own tenant via the same RLS session every other endpoint relies on.

**Explicitly deferred, not silently dropped** (this phase's own remaining backlog, carried forward):

1. **A5 — Conversational ordering (WhatsApp/IVR)**, **A6 — KYC document extraction**, **A8 — Delivery photo verification**, **A11 — Voice capture for field staff**, **A13 — MDG risk copilot**: none of this phase's other slices were touched.
2. **The actual A12 as specified** (text-to-SQL over a curated semantic layer) — this slice is a deliberately narrower, fixed-tool-menu alternative, not that design. Building true A12 (or expanding this tool registry with more tools/parameters) remains open.
3. **Complaint auto-triage (A7)** — this phase's own `PLAN.md` calls it "smallest, safest, highest immediate value... start here." It was considered as an alternative first slice (via `AskUserQuestion`) and not chosen — the user picked the Command Center precursor instead. Still a strong candidate for the next tool this registry could add, or its own structured-output-classifier slice (which would be the first real use for a plain, non-tool-calling `generate()` method on `ModelGatewayPort`, deliberately not built yet — YAGNI).

**This does not move the file's own `State` above off NOT STARTED** — this is a narrowed precursor to one slice (A12) out of this phase's much larger backlog; A5, A6, A7, A8, A11, A13 all remain untouched.

## Rules

This file follows [`planning/MODULE_STATUS.md`](../../MODULE_STATUS.md): it moves off NOT STARTED only when the gates for this phase are re-run and green, with the command output seen. Four phases in this project were marked COMPLETE here and then failed independent verification — that is why the bar is stated explicitly rather than assumed. This slice's own gates were independently re-run and are reported honestly as green (see `21-ai-foundation/STATUS.md`); they cover this slice only, not the rest of this phase's scope.

## Verification checklist

See the Verification section of `PLAN.md`. Nothing is checked off from a report; each item is re-run.
