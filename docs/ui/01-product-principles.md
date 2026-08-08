# 01 — Product Principles

## Product Vision
The LPG Agency Management Platform should feel like the operating system for a modern LPG distribution business — the kind of tool that makes a warehouse clerk, a driver, and an agency owner each feel like the software was built specifically for their job, not adapted from a generic ERP. Success looks like: a Dispatcher planning a full day's routes in under five minutes, a Driver confirming a delivery in three taps without looking away from the road for long, and an Agency Owner seeing exactly what matters — revenue, stock, outstanding payments — the second they open the Dashboard.

## UX Principles

1. **Operational speed over decoration.** Every screen is judged first by "how fast can a trained user complete their task," not by how it looks in a screenshot. Visual polish exists to *reduce* cognitive load (clear hierarchy, calm color use), never to compete with it.
2. **One primary action per screen.** Every screen has one obvious next step. Secondary actions exist but never visually compete with the primary action.
3. **Progressive disclosure.** Complex data (a full cylinder ledger history, a multi-line GST breakdown) is summarized by default and expandable on demand — never dumped on screen all at once.
4. **Consistency beats novelty.** A Data Grid behaves identically whether it's showing Orders, Customers, or Inventory. A Dispatcher who learns the platform on the Order screen should already know 90% of the Complaint screen.
5. **Forgiving by default.** Destructive actions (cancel, delete, adjust inventory) always confirm; non-destructive actions (save, filter, sort) never interrupt with a dialog.
6. **The role you're in determines what you see.** RBAC isn't just an access-control layer — it's a UX simplification tool. A Driver never sees a GST configuration screen; an Accountant never sees route-planning tools. Less surface area per role means faster comprehension.

## Design Philosophy
Visually benchmarked against Linear, Stripe Dashboard, Atlassian, Microsoft Fluent, GitHub, Vercel, and Notion — calm, high-density-when-needed, low-chrome interfaces that trust the user's competence. Never the "enterprise software" look of heavy borders, saturated primary colors everywhere, and cluttered toolbars. White space is used deliberately to group related content, not as decoration.

This is explicitly **not** a consumer app aesthetic (the Customer App is the one exception with slightly warmer, friendlier styling — see `10-color-system.md`) — the Dashboard and Driver App are working tools, styled for extended daily use, not delight-on-first-open.

## Interaction Philosophy
- **Direct manipulation where possible**: drag orders onto a route, click a table row to open detail, inline-edit where the data model allows it (per API contracts) rather than always routing through a separate edit screen.
- **Predictable, reversible**: every action either confirms before executing (destructive) or can be undone within a short window (non-destructive, e.g., form autosave with undo).
- **Keyboard-first, mouse-friendly**: every action reachable by mouse is also reachable by keyboard (`16-keyboard-shortcuts.md`), but nothing requires memorizing shortcuts to be productive on day one.

## Motion Philosophy
Motion communicates *state change*, never decorates. A row appearing in a table after a filter change animates in over 150ms so the user's eye can track what changed; a button doesn't bounce for the sake of bouncing. Full token-level detail in `09-design-tokens.md` and `20-animation-guidelines.md`. All motion respects `prefers-reduced-motion` without exception — reduced-motion isn't a "lesser" experience, it's an equally first-class one with near-instant transitions substituted.

## Accessibility Philosophy
Accessibility is not a compliance checkbox applied after design — it is a design constraint from the first sketch, consistent with the confirmed WCAG 2.2 AA requirement (D-35, `docs/srs/accessibility.md`). A screen that isn't fully keyboard-operable and screen-reader-navigable isn't "done," regardless of how it looks. Full detail: `17-accessibility.md`.

## Printing Philosophy
Every printable document (invoice, receipt, ledger statement, GST report) is designed **print-first**, not "make the web page work when printed." The printed output is the actual business artifact handed to a customer or filed for compliance — it must look intentional, correctly paginated, and legible on both thermal and A4 output. Full detail: `18-printing-ux.md`, backed by `docs/data/16-printing-data-model.md`.

## AI-Assisted Workflow Philosophy
The platform is designed to be describable and buildable by AI coding agents without ambiguity — every component, token, and screen spec in this documentation set exists specifically so a Lovable prompt (`25-lovable-prompts.md`) or an AI pair-programmer can implement a screen correctly from the spec alone, without needing to infer intent. This also means the design system favors **explicit, named patterns** (a "Data Grid," a "Wizard Form") over one-off bespoke layouts that would need to be redescribed from scratch each time.

## Non-Negotiables (Carried From Approved Documents)
- Never redesign approved business flows, state machines, or API contracts — this documentation set designs the *experience* of the already-approved system, not new business logic.
- Every color, spacing, typography, radius, shadow, animation, and icon size comes from Design Tokens (`09-design-tokens.md`) — no hardcoded values anywhere.
- Multi-tenancy, RBAC, and audit logging are UX-visible where relevant (e.g., "who approved this") but never expose cross-tenant data or bypass permission boundaries for convenience.
