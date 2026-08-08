# LPG Platform Implementation Plan

This directory contains the implementation-focused documentation for the LPG Agency Management Platform. It translates the approved business, architecture, and design documents into actionable plans for the engineering team.

The purpose of these documents is to guide the development lifecycle, from sprint planning and standards enforcement to testing and deployment. They are living documents and should be updated as the project progresses.

## Key Documents

- **[Roadmap](./roadmap.md):** Outlines the phased delivery plan, detailing what will be built in Phase 1 (MVP) and what is deferred to Phase 2.

- **[Module Implementation Plan](./module-implementation-plan.md):** Provides a detailed breakdown of each bounded context, its core components, and the sequence for implementation.

- **[Engineering Standards](./engineering-standards.md):** Defines the coding standards, patterns, and practices that must be followed across the backend, frontend, and mobile codebases.

- **[Deployment Approach](../architecture/13-deployment.md):** Describes the target cloud, containerization strategy, environment model, and CI/CD pipeline. Note that the specific Azure hosting topology and IaC tool are **deliberately deferred** to a decision before production (ADR-022).

- **[Testing Strategy](./testing-strategy.md):** Details the multi-layered approach to quality assurance, including unit, integration, end-to-end, and performance testing.

## Guiding Principles

All implementation work must adhere to the principles and decisions outlined in the `/docs` folder, particularly:
- The strategic domain model in `docs/architecture/02-domain-driven-design.md`.
- The confirmed business decisions in `docs/business/decisions.md` (D-01 … D-42).
- The architecture decisions in `docs/architecture/15-architecture-decision-records.md` (ADR-001 … ADR-026).
- The technology stack defined in `AGENTS.md`, which is authoritative on any conflict.

**Before starting any feature**, read `planning/current_phase.md` — it records the actual state of the repository and the one phase currently in progress. Documentation describes intent; that file describes reality.