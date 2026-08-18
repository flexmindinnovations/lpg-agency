# STATUS — Documentation Reconciliation & Technical Baseline

## Status

**✅ COMPLETE — re-verified end to end 2026-08-18.**

Originally closed in Phase 0. Re-opened and re-run on 2026-08-18 because four
later phases had been marked COMPLETE and then failed independent verification,
which made every documentation claim suspect until re-checked.

## What was verified, and how

Not by reading `STATUS.md` files — by running the project's own CI commands and
comparing documentation against the code, the database and the package
manifests.

| Check | Method | Result |
|---|---|---|
| Internal links | All `.md` under `docs/`, `knowledge/`, `planning/` + root | ✅ **0 broken** |
| File-path references | Every backticked `backend/…` `frontend/…` `mobile/…` path | ✅ all 11 exist |
| RBAC permission codes | Docs vs `identity.permission` | ✅ all match |
| Order state machine | `08-state-machines.md` vs `Order` aggregate vs DB CHECK | ✅ **all 10 states identical across three layers** |
| Tech-stack versions | Docs vs `pyproject.toml` / `package.json` | ⚠️ 1 stale — fixed |
| Domain events | `09-domain-events.md` vs `class X(DomainEvent)` | ❌ **badly drifted** — fixed |
| Router mounting | Every router vs `app.py` `include_router` calls | ❌ **1 dead module** — documented |

## Findings and disposition

| # | Finding | Disposition |
|---|---|---|
| 1 | **Reporting router never mounted.** Imported at `app.py:39`, never mounted. 0 of 101 OpenAPI paths match `report`; the Angular Reports page calls 4 endpoints and gets 404 on all. Every other router checked — only this one. | Documented as **C7 / R7a**. Not fixed: mounting exposes 4 endpoints to RBAC and RLS for the first time and must land with tests. |
| 2 | **Two competing phase-numbering schemes.** Driver Management built as `09-driver-management` but never added to the roadmap, so every planning directory after Phase 8 is one ahead of its roadmap row. | Fixed — full mapping table in `roadmap.md`, naming the four implemented areas with no planning directory. |
| 3 | **Domain-event catalog drifted both ways.** 10 of 18 documented events exist; 1 was renamed; **7 never implemented** — including the entire complaint pair, so the complaint domain publishes nothing despite SLA obligations. 31 implemented events undocumented. | Doc fixed with reconciliation + full catalog. Gaps logged as **C8 / R10**. |
| 4 | **`customer_address` schema doc stale** — still described the `address_line` column removed by `de17b27d462e`. | Fixed, with an explicit warning that `warehouse.address_line` and `DeliveryAddress.address_line` are different fields. |
| 5 | **Three endpoint groups undocumented** (notifications, employees, print-jobs); Reporting documented under a `/reports/` prefix that does not exist (real prefix `/reporting/`) with an async export design that was never built. | Fixed. |
| 6 | **Security architecture had no database-privilege layer.** RBAC was documented; GRANTs and RLS were not — the gap that produced the `permission denied for table employee` outage. | Written as §3.1: three authorization layers, four defect variants, and the trap that testing as `lpg_admin` passes regardless (superuser, `rolbypassrls`). |
| 7 | **One stale version claim** — signal-based change detection attributed to "Angular 20 default"; workspace is 22.0.4. | Fixed. Two other `Angular 20` mentions are historical records in a stack note and an ADR Context — correctly left. |

## Checked and found accurate

Worth recording, because both looked wrong at first glance:

- **AG Grid.** A stack note says "AG Grid Enterprise", which contradicts `package.json`. It does not — a same-day revision two lines below supersedes it with Community-as-default and Enterprise-as-optional. No Enterprise import exists anywhere in the frontend.
- **Phase 13's `/ledger/:customerId` route.** Suspected to be another unverified claim; it is wired at `app.routes.ts:50`.

## Standing rule this phase establishes

[`planning/MODULE_STATUS.md`](../../MODULE_STATUS.md) is the authority on what
is *verified*. The per-phase `STATUS.md` files and `knowledge/12-current-status.md`
record what was *built*. Where they disagree, `MODULE_STATUS.md` wins, and a row
moves to ✅ only when its gates are re-run green with the output seen.
