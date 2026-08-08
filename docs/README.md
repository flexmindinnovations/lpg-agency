# Documentation Index

Detailed specifications for the LPG Agency Management Platform.

**Read `AGENTS.md` and `knowledge/` first.** `knowledge/` holds concise summaries; this folder holds the detail behind them. Do not scan this folder exhaustively — read only what the current task needs (`AGENTS.md` §AI Context Strategy).

**What is actually being worked on right now is in [`planning/current_phase.md`](../planning/current_phase.md)**, not here. Documentation describes intent; that file describes reality.

---

## Folders

| Folder | Contents |
|---|---|
| [`business/`](./business/) | Overview, stakeholders, glossary, business rules, assumptions, **confirmed decisions D-01…D-42**, complaint management |
| [`srs/`](./srs/) | Software Requirements Specification: functional, non-functional, security, performance, accessibility |
| [`architecture/`](./architecture/) | Solution architecture 01–16, including **ADR-001…ADR-026** |
| [`architecture/superseded/`](./architecture/superseded/README.md) | Preserved .NET-era architecture documents — **historical only, do not implement from these** |
| [`data/`](./data/) | Domain model, ER diagram, **PostgreSQL physical schema**, indexing, state machines, domain events, API contracts, OpenAPI conventions, error catalog, integration contracts |
| [`ui/`](./ui/) | Product principles, personas, journeys, screens, wireframes, design system, design tokens, component specs, accessibility, printing UX |
| [`engineering/`](./engineering/) | Workflow documents (customer booking, delivery, inventory, payment, cylinder ledger) and the open-questions status tracker |
| [`implementation/`](./implementation/) | Roadmap, module implementation plan, engineering standards, testing strategy |
| [`adr/`](./adr/README.md) | Pointer to the ADR document — ADRs live in `architecture/15-architecture-decision-records.md` |

---

## Where to start

| Question | Document |
|---|---|
| What are we building, and why? | [`business/overview.md`](./business/overview.md) |
| What must it do? | [`srs/functional.md`](./srs/functional.md) |
| What did the business decide? | [`business/decisions.md`](./business/decisions.md) (D-01 … D-42) |
| Why is it built this way? | [`architecture/15-architecture-decision-records.md`](./architecture/15-architecture-decision-records.md) |
| How is the backend structured? | [`architecture/03-backend-architecture.md`](./architecture/03-backend-architecture.md) |
| How is the frontend structured? | [`architecture/04-frontend-architecture.md`](./architecture/04-frontend-architecture.md) |
| Where does code go? | [`architecture/14-folder-structure.md`](./architecture/14-folder-structure.md) |
| What do the tables look like? | [`data/03-database-schema.md`](./data/03-database-schema.md) |
| What are the API rules? | [`data/10-api-design-guidelines.md`](./data/10-api-design-guidelines.md) |
| What should the UI look like? | [`ui/08-design-system.md`](./ui/08-design-system.md), [`ui/09-design-tokens.md`](./ui/09-design-tokens.md) |
| In what order do we build it? | [`implementation/roadmap.md`](./implementation/roadmap.md) |

---

## Legacy Path Map

Documents written earlier reference a `docs/` sub-structure that **never existed in this repository**. Those references were corrected across `architecture/` and `ui/` during Phase 0, but some remain in `business/` — which is deliberate: those files are a stakeholder-approved historical record, and editing them to fix a path would alter the record for no functional gain.

Use this table to resolve any legacy reference you encounter:

| Legacy reference | Actual location |
|---|---|
| `requirements/*.md` | [`srs/`](./srs/) — `functional`, `non-functional`, `security`, `performance`, `accessibility` |
| `workflows/*.md` | [`engineering/`](./engineering/) — `customer-booking`, `delivery-flow`, `inventory-flow`, `payment-flow`, `cylinder-ledger` |
| `questions/open-questions.md` | [`engineering/open-questions.md`](./engineering/open-questions.md) |
| `business/*.md` | [`business/`](./business/) — path is correct, just relative |
| `docs/api/`, `docs/openapi/` | [`data/`](./data/) — `10-api-design-guidelines`, `11-api-contracts`, `12-openapi-specification`, `17-api-security`, `18-error-catalog` |
| `docs/security/` | [`architecture/08-security-architecture.md`](./architecture/08-security-architecture.md) and [`srs/security.md`](./srs/security.md) |
| `docs/design-system/`, `docs/ux/` | [`ui/`](./ui/) |
| `docs/printing/` | [`architecture/09-printing-architecture.md`](./architecture/09-printing-architecture.md) and [`data/16-printing-data-model.md`](./data/16-printing-data-model.md) |
| `docs/reporting/` | [`data/15-reporting-data-model.md`](./data/15-reporting-data-model.md) |
| `docs/accounting/` | [`business/business-rules.md`](./business/business-rules.md) and [`engineering/payment-flow.md`](./engineering/payment-flow.md) |
| **`modules/*.md`** | ⚠️ **Does not exist.** See below. |

### The `modules/` gap

Several documents reference per-module specification files — `modules/order-management.md`, `modules/inventory-management.md`, `modules/reporting.md`, `modules/accounting.md`, `modules/notifications.md`, `modules/customer-management.md`, `modules/complaint-management.md`. **None of these were ever created in this repository.**

The equivalent content is distributed across:

- [`srs/functional.md`](./srs/functional.md) — functional requirements per area
- [`business/business-rules.md`](./business/business-rules.md) — the BR-xx rules
- [`business/decisions.md`](./business/decisions.md) — D-xx decisions per area
- [`engineering/*.md`](./engineering/) — the operational workflows
- [`data/07-business-rules.md`](./data/07-business-rules.md), [`data/08-state-machines.md`](./data/08-state-machines.md) — rules and state machines at data level
- [`implementation/module-implementation-plan.md`](./implementation/module-implementation-plan.md) — per-module implementation scope

The only per-module document that does exist is [`business/complaint-management.md`](./business/complaint-management.md), created when D-20 elevated complaints to a full module.

This is a **known documentation gap**, recorded in [`planning/current_phase.md`](../planning/current_phase.md). It is not blocking: every module's requirements are documented somewhere, just not consolidated per module. Consolidation would be worthwhile before each module's implementation phase.

---

*Index created during Phase 0 — Documentation Reconciliation, 2026-08-09.*
