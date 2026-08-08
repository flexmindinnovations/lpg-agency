# Development Workflow

## Purpose

This document defines the standard development workflow for the LPG Agency Management Platform.

It provides a repeatable process for developers and AI coding agents to follow when planning, implementing, reviewing, testing, and documenting new features.

The objective is to ensure consistency, maintainability, and production-quality software throughout the project lifecycle.

---

# Development Philosophy

The project follows an **AI-assisted, documentation-first, architecture-driven** development approach.

Every implementation must be guided by:

- Business Requirements
- Architecture
- Engineering Standards
- Design System
- API Contracts
- Existing Codebase

Code should never be written without understanding the business context.

---

# Development Lifecycle

Every feature follows the same lifecycle.

```

Business Requirement
↓
Architecture Review
↓
Technical Planning
↓
Implementation
↓
Testing
↓
Code Review
↓
Documentation Update
↓
Commit
↓
Deploy

```

No step should be skipped.

---

# AI Context Loading Order

Before implementing any feature, always read the following files in order:

1. `README.md`
2. `AGENTS.md`
3. `planning/current_phase.md` — **what is actually being worked on now**
4. `knowledge/12-current-status.md`
5. `knowledge/00-project-overview.md`
6. `knowledge/01-business-domain.md`
7. `knowledge/03-architecture-summary.md`
8. `knowledge/02-tech-stack.md`
9. `knowledge/07-ui-ux-summary.md`
10. `knowledge/09-engineering-standards.md`
11. `knowledge/10-feature-map.md`

Then the current feature's `planning/features/<feature>/PLAN.md`, `TASKS.md`, and `STATUS.md`.

Only after understanding the summaries should the AI read the detailed documentation for the requested feature.

> **Corrected in Phase 0 (2026-08-09).** This list previously named five knowledge files that do not exist (`02-architecture-summary.md`, `03-technology-stack.md`, `04-ui-ux-summary.md`, `05-engineering-standards.md`, `06-feature-map.md`). An agent following it literally would have failed to load context. The numbering above matches the actual files.

---

# Feature Development Workflow

For every feature:

## Step 1 — Understand the Business

Read:

- Business Domain Summary
- Relevant SRS
- Business Rules

Understand:

- Why the feature exists
- Business objectives
- Business constraints
- Actors
- Expected outcome

Never implement a feature without understanding its business purpose.

---

## Step 2 — Review Architecture

Read:

- Architecture Summary
- Relevant ADRs
- Data Summary
- API Contracts

Verify:

- Layer responsibilities
- Module ownership
- Dependencies
- Security implications

Never violate architecture.

---

## Step 3 — Review Existing Code

Before creating anything:

Search for:

- Existing services
- Components
- Utilities
- Hooks
- Guards
- Validators
- DTOs
- Models

Reuse existing code whenever possible.

Avoid duplication.

---

## Step 4 — Create an Implementation Plan

Before writing code, define:

- Files to create
- Files to modify
- Business rules affected
- APIs affected
- Database changes
- UI changes
- Tests required

Do not start implementation without a plan.

---

## Step 5 — Implement Incrementally

Implement in small logical steps.

Typical order:

1. Domain
2. Repository
3. Service
4. API
5. Frontend
6. Tests

Avoid implementing multiple unrelated features in one change.

---

## Step 6 — Testing

Every feature should include:

- Unit Tests
- Integration Tests
- Component Tests (UI)
- API Tests
- Accessibility Tests (where applicable)

Critical business logic must always be tested.

---

## Step 7 — Documentation

Update documentation when:

- Business rules change
- API changes
- Database changes
- UI changes
- Architecture changes

Documentation is part of the feature.

---

## Step 8 — Code Review

Verify:

- Business correctness
- Architecture compliance
- Security
- Accessibility
- Performance
- Maintainability
- Tests

Only then should the feature be considered complete.

---

# Pull Request Checklist

Every Pull Request should include:

- Clear description
- Related requirement
- Screenshots (if UI)
- API examples (if backend)
- Tests
- Documentation updates

---

# Commit Strategy

Keep commits small.

Each commit should represent one logical change.

Good examples:

feat(customer): add customer registration

fix(delivery): resolve inventory synchronization

refactor(accounting): simplify payment validation

Avoid:

update

changes

fix

work

misc

---

# Refactoring Rules

Before refactoring:

- Understand existing behavior.
- Preserve business rules.
- Preserve API contracts.
- Preserve tests.

Refactor only when it improves:

- Readability
- Maintainability
- Performance
- Reusability

Never refactor unrelated code while implementing a feature.

---

# Dependency Management

Before adding a dependency:

Verify:

- Existing project libraries cannot solve the problem.
- The dependency is actively maintained.
- The dependency has a compatible license.
- The dependency is secure.

Avoid duplicate libraries.

---

# AI Coding Rules

Before generating code:

✔ Read the relevant documentation.

✔ Understand the business context.

✔ Search for existing implementations.

✔ Follow project architecture.

✔ Reuse existing components.

✔ Follow coding standards.

✔ Write tests.

✔ Update documentation if required.

Never:

- Invent requirements.
- Ignore architecture.
- Duplicate business logic.
- Introduce unnecessary abstractions.
- Add unapproved libraries.
- Break tenant isolation.
- Hardcode UI values.

---

# Error Recovery Workflow

If implementation fails:

1. Read the error carefully.
2. Inspect logs.
3. Identify root cause.
4. Review relevant documentation.
5. Fix the issue.
6. Add tests if needed.
7. Verify the fix.

Avoid trial-and-error programming.

---

# Definition of Complete

A feature is complete only when:

- Business requirements are satisfied.
- Architecture is respected.
- Code passes quality standards.
- Tests pass.
- Accessibility is verified.
- Documentation is updated.
- Code review is complete.

---

# AI Decision Making

When multiple solutions exist:

Choose the solution that:

- Is simplest.
- Fits existing architecture.
- Maximizes reuse.
- Minimizes technical debt.
- Is easiest to maintain.
- Improves readability.

Always explain architectural trade-offs before making significant changes.

---

# Related Documentation

Refer to:

- AGENTS.md
- docs/architecture/
- docs/engineering/
- docs/business/
- docs/ui/
- docs/data/