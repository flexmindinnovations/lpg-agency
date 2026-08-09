# 17 — Accessibility

## Purpose
Defines the platform's WCAG 2.2 AA implementation across ARIA usage, screen readers, focus management, reduced motion, color contrast, touch targets, accessible tables, accessible charts, accessible forms, and accessible dialogs — the UX-level realization of the confirmed D-35 requirement and `docs/architecture/11-accessibility-strategy.md`.

## 1. Standard and Scope
WCAG 2.2 Level AA, required at launch (not deferred), applied to the Dashboard's full component library and every screen built from it, and to the mobile apps via platform-native accessibility APIs (Flutter Semantics).

## 2. ARIA Usage
- Semantic HTML first — native elements (button, table, nav, dialog-appropriate markup) are used wherever possible; ARIA roles/attributes are added only where semantic HTML alone can't express the interaction (e.g., a custom Data Grid, a custom Combobox).
- ARIA is never used to "fix" a non-semantic element when a semantic one would work — a styled div pretending to be a button via role="button" is only acceptable where no native alternative exists.

## 3. Screen Readers
- Every interactive component tested with NVDA + Chrome and VoiceOver + Safari as part of its Definition of Done.
- Live regions (aria-live="polite") announce: bulk-selection count changes, form submission results, real-time status updates (Order status changes on the Live Delivery Tracking screen) — never aria-live="assertive" except for genuinely urgent, rare interruptions (there are none identified in this platform's Phase 1 scope; assertive live regions are avoided as a default pattern).

## 4. Focus Management
- Every Dialog/Drawer traps focus while open and returns focus to the triggering element on close (`13-component-specifications.md` Worked Spec 3).
- Route transitions in the Dashboard move focus to the new page's primary heading, so keyboard/screen-reader users are never stranded on a stale focus target.
- Focus-visible indicators (never suppressed) use a 2px outline in color-action-primary with sufficient contrast against all three themes (`10-color-system.md` section 6).

## 5. Reduced Motion
Every animation in `20-animation-guidelines.md` has a defined reduced-motion variant (near-instant, opacity-only) automatically applied when prefers-reduced-motion is set — no component requires per-instance opt-in, since the reduced-motion token set (`09-design-tokens.md` section 7) is applied globally at the theme level.

## 6. Color Contrast
Full detail `10-color-system.md` section 6 — 4.5:1 body text, 3:1 large text and interactive borders, verified per theme (Light/Dark/High Contrast) and re-verified whenever a tenant sets a custom branding color (`10-color-system.md` section 5's automated contrast-checking fallback).

## 7. Touch Targets
- Minimum 44x44dp (Dashboard/tablet contexts) and 48x48dp (Driver App, given the outdoor/gloved usage context, `02-user-personas.md`) for every interactive element, including icon-only buttons.
- Adjacent touch targets maintain at least 8px spacing to prevent accidental mis-taps, especially relevant on the Warehouse Staff and Driver personas' shared-device/gloved contexts.

## 8. Accessible Tables (Data Grid)
Full detail `14-data-grid-guidelines.md` section 12 — grid/row/gridcell roles, aria-sort, live-region selection announcements, virtualization-aware row counts.

## 9. Accessible Charts
- Every chart (`12-component-library.md`) ships with a paired, visually-hidden (but screen-reader-accessible) data table containing the same underlying values — a screen reader user never has access to less information than a sighted user viewing the visual chart.
- Chart color-coding is never the sole differentiator between series — paired with distinct line styles (solid/dashed/dotted) or direct data labels where feasible.

## 10. Accessible Forms
Full detail `15-form-guidelines.md` section 9 — programmatic labels, required-field indication beyond color, associated and announced error messages, automatic focus-to-first-error on failed submit.

## 11. Accessible Dialogs
Full detail `13-component-specifications.md` Worked Spec 3 — dialog role, aria-modal, labeled via title reference, focus trap, focus restoration.

## 12. Testing & Validation
- Automated: axe-core integrated into Storybook (dev-time) and CI (Playwright + axe-core on critical flows) as a merge-blocking gate.
- Manual: screen-reader walkthroughs of critical flows (Booking, Order Approval, Invoice Generation, Delivery Confirmation) before every release, since automated tools catch roughly a third to half of real-world accessibility issues at best.

## Best Practices
- Accessibility acceptance criteria are part of every screen's Definition of Done (`26-design-review-checklist.md`), never a separate, deferrable workstream.
- New third-party component adoption (e.g., a specific PrimeNG, AG Grid, or Angular Material feature) is accessibility-audited before adoption, since inheriting an inaccessible third-party widget undermines the shared-library accessibility strategy.

## Risks
- Data Grid complexity is the single highest-risk area for accessibility regressions given AG Grid's feature surface (Community by default, Enterprise where a feature enables it per ADR-028) — mitigated by concentrating extra manual testing effort there specifically.
- Tenant branding color customization is the highest risk to consistent contrast compliance across tenants — mitigated by the automated contrast-checking fallback (`10-color-system.md` section 5).

## Alternatives Considered
- Per-feature accessibility ownership (each feature team handles its own ARIA/keyboard logic) — rejected; inconsistent quality versus the shared-component-library-first approach (`08-design-system.md`).

## Future Scalability
- Expand automated coverage beyond axe-core toward more comprehensive automated-plus-assistive-technology-user-testing programs as the platform matures post-launch.
