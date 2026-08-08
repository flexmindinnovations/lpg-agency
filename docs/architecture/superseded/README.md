# Superseded Architecture Documents

## ⛔ Nothing in this folder is current. Do not implement from any document here.

This folder preserves the original `docs/architecture/` documents that were written against an **ASP.NET Core 8 / C# / EF Core / MediatR / Azure SQL / SignalR** technology stack, before the platform's backend stack was confirmed as **Python 3.13 / FastAPI / SQLAlchemy 2.x / PostgreSQL / Redis**.

They are retained — never deleted — so the reasoning behind the change stays traceable, exactly as the ADR document's own review policy requires: *"superseded decisions are marked Superseded, with a link to the new ADR, never deleted, preserving the historical reasoning trail."*

---

## Why these documents exist

The platform's documentation was produced in layers. The business analysis, SRS, and UX layers are technology-neutral and were unaffected. The **architecture layer** was authored against .NET. The **data layer** (`docs/data/`, 20 documents) was authored later, against Python/FastAPI/PostgreSQL — including a complete PostgreSQL physical schema.

Both layers remained in the repository, each internally consistent, each looking authoritative. `AGENTS.md` — which declares itself the authoritative source on any conflict — specifies Python/FastAPI/PostgreSQL, and `knowledge/` agrees with it.

The Phase 0 reconciliation resolved this in favour of `AGENTS.md`. The .NET architecture was **never implemented**; no code was ever written against it.

## What replaced what

| Superseded document | Replaced by | Superseding ADR(s) |
|---|---|---|
| `01-system-architecture-dotnet.md` | [`../01-system-architecture.md`](../01-system-architecture.md) | ADR-012 |
| `03-backend-architecture-dotnet.md` | [`../03-backend-architecture.md`](../03-backend-architecture.md) | ADR-012, ADR-014, ADR-017, ADR-023, ADR-024 |
| `06-database-architecture-dotnet.md` | [`../06-database-architecture.md`](../06-database-architecture.md) | ADR-013, ADR-017 |
| `09-printing-architecture-dotnet.md` | [`../09-printing-architecture.md`](../09-printing-architecture.md) | ADR-016 (ADR-010 itself still stands) |
| `13-deployment-dotnet.md` | [`../13-deployment.md`](../13-deployment.md) | ADR-022 |
| `14-folder-structure-dotnet.md` | [`../14-folder-structure.md`](../14-folder-structure.md) | ADR-012, ADR-018, ADR-025 |

Full supersession rationale for each decision is in [`../15-architecture-decision-records.md`](../15-architecture-decision-records.md).

## Architecture documents that were *not* superseded

These remain current on the active path. Where they contained incidental .NET references (a library name, a diagram node), those were corrected in place — the documents' substance was always stack-independent:

| Document | Note |
|---|---|
| `02-domain-driven-design.md` | Bounded contexts, aggregates, ubiquitous language — unchanged; domain-event dispatch mechanism rebound to Python |
| `04-frontend-architecture.md` | Revised for Angular 22 (from 20), AG Grid Enterprise, WebSocket transport — Nx and Signals-first direction retained |
| `05-mobile-architecture.md` | Flutter/Riverpod/Drift — entirely unaffected |
| `07-api-architecture.md` | REST/versioning/pagination unchanged; validation and authorization mechanisms rebound to FastAPI |
| `08-security-architecture.md` | Security model unchanged; identity and query-parameterization mechanisms rebound |
| `10-performance-strategy.md` | Strategy unchanged; datastore and ORM specifics rebound |
| `11-accessibility-strategy.md` | WCAG 2.2 AA strategy — entirely unaffected |
| `12-observability.md` | Observability model unchanged; logging and tracing libraries rebound |
| `15-architecture-decision-records.md` | Amended in place; this is where supersession is recorded |

## Which decisions survived the stack change

Worth stating plainly, because the change was narrower than the volume of edited text suggests. These decisions were made on stack-independent grounds and still hold:

- **ADR-001** — monorepo for backend + all three clients
- **ADR-002** — modular monolith over microservices for Phase 1
- **ADR-003** — shared database, shared schema, tenant-discriminator multi-tenancy
- **ADR-006** — Flutter for both mobile apps
- **ADR-008** — offline-first Driver App only
- **ADR-009** — URL-segment API versioning
- **ADR-010** — server-rendered, template-based printing engine
- **ADR-011** — shared component library as the accessibility enforcement mechanism

What actually changed: the backend language and framework, the ORM, the relational engine, the in-process mediation mechanism, the real-time transport, and the rendering libraries.

## Reading these documents

If you are looking for historical context — *"why was Azure SQL chosen over Cosmos DB?"*, *"what were the five MediatR pipeline behaviors meant to enforce?"* — these documents are a legitimate source, and the second question in particular is worth understanding, because those five behaviors encode BR-28 (audit logging) and BR-30 (tenant scoping) and were deliberately re-expressed rather than dropped.

If you are looking for guidance on what to build, use the active path.

---

**Superseded:** 2026-08-09 · **Phase 0 — Documentation Reconciliation** · see [`planning/features/00-documentation-reconciliation/`](../../../planning/features/00-documentation-reconciliation/PLAN.md)
