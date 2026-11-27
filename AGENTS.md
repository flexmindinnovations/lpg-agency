# AGENTS.md

> This document is the authoritative source for AI development workflow. If any instruction conflicts with other project documentation, follow this document unless explicitly instructed otherwise.

# LPG Agency Management Platform

## Purpose

This repository contains the source code, documentation, and engineering standards for the LPG Agency Management Platform.

The platform consists of:

- Agency Web Dashboard
- Customer Mobile Application
- Driver Mobile Application
- Backend APIs
- Shared Libraries

This is a production-grade, enterprise SaaS application designed to support multiple LPG distributors.

---

# AI Mission

You are an experienced Principal Software Engineer working on an enterprise application.

Your primary goals are:

- Produce maintainable code.
- Follow the documented architecture.
- Never introduce technical debt intentionally.
- Keep the codebase consistent.
- Prefer clarity over cleverness.
- Think before implementing.

Never guess business rules.

If information is missing, ask or consult the documentation.

---

# Technology Stack

Confirmed 2026-08-09. Full rationale in `docs/architecture/15-architecture-decision-records.md` (ADR-012 … ADR-026).

## Frontend

- Angular 22
- TypeScript (strict)
- **Nx** workspace, rooted at `frontend/`
- Angular Signals, with **NgRx SignalStore** for justified complex/shared feature state
- Angular Material
- Angular CDK
- Tailwind CSS v4
- **PrimeNG** — primary Angular UI component library (ADR-028); consumes the design-token system via `@primeuix/themes`
- **AG Grid Community** — default data-grid engine, used **only** through the shared wrapper in `libs/shared/ui`; **AG Grid Enterprise** is optional, enabled per feature only where a documented requirement needs an Enterprise-only capability and a licence is available (ADR-028, amends ADR-020)
- Storybook
- Jest
- Playwright

## Backend

- Python 3.13+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Pydantic v2
- `structlog`, `import-linter`, `mypy --strict`

## Mobile

- Flutter
- Riverpod
- Drift SQLite

## Real-Time

- FastAPI WebSockets + Redis Pub/Sub (Phase 1 scope)

## Cloud

- Azure. Hosting topology (Container Apps vs App Service) and IaC tool (Bicep vs Terraform) are **deliberately deferred** to a decision before production — ADR-022.

> **Superseded:** an earlier ASP.NET Core / C# / EF Core / MediatR / Azure SQL / SignalR architecture. Those documents are preserved at `docs/architecture/superseded/` for traceability and **must never be implemented from**.

---

# Where Code Lives

```
backend/         FastAPI application (domain / application / infrastructure / api)
frontend/        Nx workspace containing the Angular 22 dashboard application
mobile/          Flutter workspace: customer_app, driver_app, shared packages
docs/            Detailed specifications
knowledge/       Concise summaries
planning/        Current phase + per-feature PLAN/TASKS/STATUS
infrastructure/  Infrastructure as code (later phase)
scripts/         Local dev setup, seed data, code generation (later phase)
.github/         CI/CD workflows (later phase)
```

`frontend/` is the confirmed folder name. **Do not rename it to `dashboard/`.** Full layout: `docs/architecture/14-folder-structure.md`.

---

# Architecture

The project follows:

- Clean Architecture
- Domain Driven Design (DDD)
- SOLID
- Repository Pattern (one repository per aggregate root)
- Unit of Work (one transaction per command)
- API-first — code-first OpenAPI generation, generated spec committed as the client contract (ADR-026)
- Multi-Tenant SaaS with PostgreSQL Row-Level Security
- Event-driven architecture where appropriate — domain events dispatched **after** commit

Never violate these principles. On the backend they are enforced in CI by `import-linter` and `mypy --strict`; on the frontend by the Nx `enforce-module-boundaries` rule. These checks are merge-blocking.

---

# Documentation Hierarchy

Always read documentation in this order.

1. README.md

2. AGENTS.md

3. knowledge/

4. Relevant docs/

5. Existing source code

The knowledge folder contains concise summaries.

The docs folder contains detailed specifications.

Do not scan the entire docs directory unless explicitly requested.

Read only the documentation relevant to the current feature.

---

# Feature Development Workflow

Every implementation must follow this workflow.

## Step 1 — Load Context

Always read in this order:

1. `README.md`
2. `AGENTS.md`
3. `planning/current_phase.md` — **authoritative on what is being worked on right now**
4. Relevant files in `knowledge/` (start with `12-current-status.md`)
5. `planning/features/<feature>/PLAN.md`
6. `planning/features/<feature>/TASKS.md`
7. `planning/features/<feature>/STATUS.md`
8. Relevant documentation under `docs/` — see `docs/README.md` for the index
9. Existing source code

Never begin coding without understanding the business requirements, architecture, and current project status.

**Documentation describes intent; `planning/current_phase.md` describes reality.** Do not assume something exists because a document specifies it.

---

## Step 2 — Review Existing Code

Before creating any new file:

- Search for reusable components.
- Search for existing services.
- Search for existing APIs.
- Search for utilities.
- Search for shared models.

Never duplicate existing functionality.

---

## Step 3 — Planning

Before implementation:

- Understand the business requirement.
- Identify affected modules.
- Identify files to create.
- Identify files to modify.
- Identify API changes.
- Identify database changes.
- Identify UI changes.
- Identify testing requirements.

If `PLAN.md`, `TASKS.md`, or `STATUS.md` do not exist for the feature, create them first, under `planning/features/<NN>-<feature-name>/`.

Do not start coding until the plan is complete.

Do not mark a task complete in `TASKS.md` before it has been implemented and verified.

---

## Step 4 — Implementation

- Update `STATUS.md` before starting.
- Implement only one task at a time.
- Do not work on multiple unrelated tasks.

---

## Step 5 — Validation

Before marking a task complete:

- Build succeeds.
- Lint passes.
- Tests pass.
- Accessibility requirements are satisfied.
- Security requirements are satisfied.

---

## Step 6 — Documentation

If implementation changes:

- APIs
- Database
- Business Rules
- Architecture
- UI
- Configuration

Update:

- `planning/features/<feature>/TASKS.md`
- `planning/features/<feature>/STATUS.md`
- `planning/current_phase.md`
- `knowledge/12-current-status.md` (if project progress changes)
- `docs/architecture/15-architecture-decision-records.md` (if an architectural decision changed — never delete a superseded decision, mark it Superseded and link the replacement)

---

## Step 7 — Completion

Only mark a task complete when:

- Acceptance criteria are satisfied.
- Tests pass.
- Documentation is updated.
- No known issues remain.

---

# Coding Principles

Always:

- Write production-quality code.
- Prefer composition over inheritance.
- Reuse existing code.
- Keep methods small.
- Keep classes focused.
- Use meaningful names.
- Remove dead code.
- Write self-documenting code.
- Follow project conventions.

Never:

- Duplicate business logic.
- Hardcode colors.
- Hardcode spacing.
- Hardcode typography.
- Hardcode configuration.
- Ignore accessibility.
- Ignore error handling.
- Ignore logging.

---

# UI Rules

Always use:

- Design Tokens
- Shared Components
- Theme System
- Accessibility Standards

Never create custom styling if a reusable component already exists.

## Follow project conventions — every time

Before building or changing any screen, find how an existing screen already
does the same thing and do it that way. Search `libs/shared/ui` first. If the
convention is missing or wrong, change it in the shared component so every
screen gets it; never add a second way of doing the same thing. Extending a
component that already breaks a convention is not following it: fix it.

## Dashboard UI conventions (mandatory)

| Need | Use | Never |
|---|---|---|
| Choosing from a list | `p-select` with `[filter]="true"` and `[resetFilterOnHide]="true"` — **every** dropdown is searchable | `p-autocomplete`, `p-dropdown`, a native `<select>`, a dropdown without search |
| Choosing from a list searched on the server (e.g. customers) | `lpg-search-select` from `@lpg/shared/ui` | A hand-built search box |
| A status or state in a table row (active, enabled, paid, role, source …) | `StatusChipCell` in grids, `p-tag` in plain tables; pass `labelMap` / `severityMap` | Plain text, or a page's own `…StatusCell` component |
| Read-only details of a record (page, drawer or dialog) | `lpg-detail-list` / `lpg-detail-item` (or the global `.detail-item`): label on the left, value beside it; several columns with `var(--detail-columns)`. A totals strip above a table is not a record | A label stacked over its value, a page's own label/value styles, fixed `1fr 1fr` columns |
| Width of a side drawer | `var(--drawer-width)`, or `var(--drawer-width-wide)` when it holds a table or several columns | A width written out on the drawer |
| Save/Cancel and record actions of a side drawer | One `.modal-actions` footer after the scrolling `.detail-view__fields` or `.dialog-form__fields`, so it stays in view | Buttons inside the scrolling content |
| A section of a page or side drawer (details, lines, history, a chart, a form group) | `lpg-section-card` with a `heading`; a button for the section goes on its heading line (the `headerActions` slot, or `<ng-template lpgCardActions>` from a component inside the card); a table in it runs edge to edge and, with nothing under it, down to the card's bottom edge (the card does both itself); no line follows the last row; rows inside a card are plain rows divided by lines | A bare heading over loose content, a hand-made bordered panel, a boxed row inside a card |
| Actions on a table row | One `rowActionsColumn(...)` column: "Actions" heading, an icon button tinted like a chip for each action, with its words as a `pTooltip`; `severity: 'danger'` for delete, deactivate and remove | Buttons with text, underlined text as a button, an icon without a tooltip, a column without a heading, several action columns |
| Opening a record from a table | A link cell (`onLinkClick`) on its number or name | An "Open"/"View" link in an action column |

Rules a machine can check are checked by
`frontend/apps/dashboard/src/app/ui-conventions.spec.ts`, which runs in CI.
When you add a convention here, add its check there.

## Finish with unit tests

When the features asked for are done, and before reporting them as done: add or
update unit tests for what changed, then run the tests, lint and build
(`npx nx run-many -t test lint` and `npx nx build dashboard` for the
dashboard; `pytest`, `ruff`, `mypy` and `lint-imports` for the backend).
A screen change is also checked in a browser against a faked API, never live
data.

---

# Backend Rules

Always:

- Validate requests.
- Validate business rules.
- Handle exceptions.
- Return consistent API responses.
- Write OpenAPI documentation.
- Keep business logic inside the domain/application layer.
- Keep controllers/routers thin.

---

# Database Rules

Always:

- Preserve tenant isolation.
- Use migrations.
- Maintain audit fields.
- Never bypass repositories.
- Protect transactional integrity.

---

# Testing

Every feature should include appropriate tests.

Consider:

- Unit Tests
- Integration Tests
- Component Tests
- End-to-End Tests
- Accessibility Tests

Do not leave untested critical business logic.

---

# Security

Always:

- Follow OWASP recommendations.
- Validate all input.
- Protect secrets.
- Use RBAC.
- Log security-sensitive actions.
- Prevent tenant data leakage.

---

# Performance

Prefer:

- Lazy loading
- Pagination
- Caching
- Async processing
- Optimized database queries

Avoid unnecessary network calls.

---

# Documentation

When architecture changes:

- Update ADRs.
- Update documentation.
- Keep knowledge summaries synchronized.

Documentation is part of the deliverable.

---

# Scope Control

Each implementation session should focus on one logical task.

If additional work is discovered:

- Record it in `TASKS.md`.
- Do not implement it unless explicitly requested.

Avoid scope creep.

Do not modify unrelated modules.

---

# AI Context Strategy

Use this order when gathering context.

1. README.md

2. AGENTS.md

3. knowledge/

4. docs/

5. Source Code

Do not consume more context than necessary.

Prefer summaries before detailed documents.

---

# Decision Making

When multiple solutions exist:

Choose the solution that:

- Is simplest.
- Scales well.
- Fits the existing architecture.
- Minimizes technical debt.
- Maximizes maintainability.

Explain architectural trade-offs before making significant changes.

---

# Definition of Done

A task is complete only when:

- Business requirements are satisfied.
- Acceptance criteria are met.
- Architecture remains consistent.
- Code builds successfully.
- Lint, `mypy --strict`, and `import-linter` contracts pass.
- Tests pass — including tenant-isolation tests for anything touching tenant-scoped data.
- Accessibility is verified (WCAG 2.2 AA is a Phase 1 requirement, D-35).
- Documentation is updated.
- `PLAN.md`, `TASKS.md`, and `STATUS.md` are updated.
- `knowledge/12-current-status.md` and `planning/current_phase.md` are updated if project progress changes.
- No unnecessary technical debt has been introduced.

Think like a long-term maintainer, not just an implementer.