# Feature Development Rules

## Purpose

This document defines the mandatory workflow for implementing any feature in the LPG Agency Management Platform.

Every developer and AI coding agent must follow these rules.

These rules apply to:

- Cline
- Claude Code
- GitHub Copilot
- ChatGPT
- Future AI coding assistants

---

# Core Principle

Never build multiple business features simultaneously.

Always complete one feature before starting another.

Every feature must be:

- Planned
- Designed
- Implemented
- Tested
- Documented
- Reviewed

---

# Development Order

Always follow this order.

Repository

↓

Infrastructure

↓

Authentication

↓

Shared Components

↓

Business Modules

↓

Reports

↓

Administration

↓

AI Features

Never skip dependencies.

---

# Feature Workflow

Every feature follows these phases.

## Phase 1

Understand the Business

Read

- README.md
- AGENTS.md
- knowledge/
- Relevant docs

Understand

- Business Goal
- Actors
- Workflow
- Rules
- Edge Cases

Do not write code yet.

---

## Phase 2

Planning

Create an implementation plan.

Include

- Files to Create
- Files to Modify
- APIs
- Database Changes
- UI Changes
- Tests

Wait until the plan is complete.

---

## Phase 3

Architecture Validation

Verify

- Clean Architecture
- DDD
- SOLID
- Existing Patterns

Never violate architecture.

---

## Phase 4

Backend

Implement in this order.

Domain

↓

Application

↓

Repository

↓

API

↓

Tests

Never start frontend first.

---

## Phase 5

Frontend

Implement

Models

↓

API Client

↓

Signals

↓

Components

↓

Pages

↓

Routing

↓

Testing

Use reusable components only.

---

## Phase 6

Mobile

If required

Implement

Customer App

Driver App

Only after backend APIs exist.

---

## Phase 7

Testing

Create

Unit Tests

Integration Tests

API Tests

Accessibility Tests

E2E Tests (where applicable)

---

## Phase 8

Documentation

Update

API

Architecture

Knowledge

Feature Docs

If behavior changed.

---

# Required Checklist

Before implementation verify

☐ Business understood

☐ Existing implementation checked

☐ Reusable components identified

☐ API contract reviewed

☐ Database reviewed

☐ Security reviewed

☐ Accessibility reviewed

☐ Printing requirements reviewed

---

# Coding Rules

Always

- Reuse existing code
- Use Design Tokens
- Use strict typing
- Write production-quality code
- Handle errors
- Validate input
- Log important operations

Never

- Hardcode values
- Duplicate code
- Ignore architecture
- Ignore tenant isolation
- Ignore accessibility
- Ignore tests

---

# Feature Completion Checklist

A feature is complete only when

☐ Business requirements satisfied

☐ Backend complete

☐ Frontend complete

☐ Mobile complete (if applicable)

☐ Tests passing

☐ Accessibility verified

☐ Documentation updated

☐ Code reviewed

---

# Definition of Done

The feature can be considered complete only when

- Code compiles
- Tests pass
- Documentation updated
- No TODOs remain
- No hardcoded values
- No duplicated code
- No lint errors
- No type errors

---

# AI Rules

Before generating code

Always

1. Read AGENTS.md

2. Read knowledge/

3. Read feature documentation

4. Search existing implementation

5. Explain implementation plan

6. Then write code

Never

- Assume business rules
- Invent APIs
- Invent database schema
- Skip validation
- Skip testing