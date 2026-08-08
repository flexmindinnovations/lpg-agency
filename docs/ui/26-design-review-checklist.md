# 26 — Design Review Checklist

## Purpose
A checklist for reviewing every screen before it's considered design-complete, covering UX, accessibility, performance, consistency, printing, keyboard navigation, responsive behavior, and enterprise readiness.

## How to Use
Every screen (per `05-screen-inventory.md`) must pass this checklist before implementation begins, and again before release. A reviewer who cannot check every applicable box either fixes the gap or explicitly documents why an item is not applicable, never silently skips it.

## UX
- Screen has exactly one clear primary action (Product Principle 2, `01-product-principles.md`).
- Screen matches its assigned template (List/Detail/Action, `07-wireframe-specifications.md`) or has a documented, reviewed reason for deviating.
- All four states specified: Loading, Empty, Error, Success (`07-wireframe-specifications.md`, `21-empty-error-success-states.md`).
- Copy is clear, action-oriented, and free of internal jargon a Warehouse Staff or Customer persona wouldn't understand.
- Destructive actions confirm before executing; non-destructive actions never interrupt with a confirmation dialog.

## Accessibility
- WCAG 2.2 AA contrast verified across Light, Dark, and High Contrast themes (`10-color-system.md`).
- All interactive elements keyboard-reachable and operable, with visible focus indicators.
- Screen reader walkthrough completed (NVDA/Chrome and VoiceOver/Safari for Dashboard; TalkBack/VoiceOver for mobile).
- All images/icons have appropriate alt text or accessible labels; no information conveyed by color alone.
- Touch targets meet minimum size (44dp Dashboard/tablet, 48dp Driver App, `17-accessibility.md` section 7).
- Forms meet the accessible-forms requirements in `15-form-guidelines.md` section 9.
- Automated axe-core scan passes with zero critical/serious violations.

## Performance
- Large lists use virtual scrolling and server-side pagination (`14-data-grid-guidelines.md`), never an unbounded client-side dataset.
- Heavy/below-the-fold content uses deferred loading (`23-angular-design-guidelines.md` section 5) where applicable.
- No layout shift on content load (skeleton screens reserve the correct space).
- Screen meets the confirmed performance SLAs (dashboard load under 2s, API response under 300ms average, per the approved Architecture documents).

## Consistency
- Every color, spacing, typography, radius, shadow, motion, and icon value traces to a Design Token (`09-design-tokens.md`) — zero hardcoded values.
- Component usage matches `12-component-library.md`/`13-component-specifications.md` — no bespoke one-off patterns without a documented, reviewed justification.
- Terminology matches the approved domain model/state machines exactly (e.g. Order status labels are never reworded differently between screens or apps).
- Navigation/breadcrumb behavior matches `04-information-architecture.md`.

## Printing (Where Applicable)
- Print Preview renders identically to the final printed/PDF output (`18-printing-ux.md` section 2).
- Mandatory legal/tax blocks (GST breakdown) are visually distinct and non-removable in tenant customization.
- Barcode/QR codes tested for scannability at actual print resolution, not just on-screen appearance.
- Multi-page documents have correct page breaks, running headers, and an end-of-document marker.

## Keyboard Navigation
- Full keyboard operability confirmed — every mouse-accessible action has a keyboard path (`16-keyboard-shortcuts.md`).
- Tab order follows visual/logical hierarchy.
- Dialogs/Drawers trap focus and restore it correctly on close.
- Data Grid keyboard navigation matches `14-data-grid-guidelines.md` section 9 exactly.
- No keyboard shortcut collides with an existing global or module-specific binding.

## Responsive Behavior
- Screen verified at all applicable breakpoints for its target app (`19-responsive-design.md`).
- Tablet breakpoint explicitly tested, not assumed to just work between desktop and mobile.
- Touch and hover interactions both have equivalent affordances on touch-capable devices.
- Mobile Dashboard access (where supported) degrades gracefully rather than rendering a broken cramped layout.

## Enterprise Readiness
- RBAC/permission scoping verified — the screen shows/hides/enables only what the current role's permissions allow (docs/data/17-api-security.md permission matrix).
- Multi-tenant isolation verified — no cross-tenant data ever visible, even transiently during loading states.
- Audit-relevant actions (approvals, cancellations, adjustments) are visually distinct and clearly attributed once completed.
- Error messages never leak internal implementation details (stack traces, raw SQL, internal IDs beyond what the user already has).
- Offline behavior (where applicable, Driver App primarily) tested with connectivity genuinely disabled, not just simulated in devtools.

## Sign-Off
A screen is design-complete only when every applicable item above is checked by both a designer and an accessibility reviewer (may be the same person for smaller teams, but the check must be performed as a distinct pass, not folded into general design review). Any unchecked item requires either a fix or a documented, dated exception with a named owner and follow-up plan.

## Best Practices
- This checklist is applied identically regardless of screen complexity — a simple screen still passes through every section, even if most items resolve quickly as trivially satisfied.
- Checklist failures found post-launch are logged against the specific screen and tracked to resolution with the same rigor as a functional bug, not treated as lower-priority polish.

## Risks
- Checklist fatigue on a 61-screen inventory could lead to superficial box-checking — mitigated by pairing the checklist with the automated gates already described elsewhere (axe-core in CI, visual regression via Storybook/Chromatic) so at least the accessibility and consistency sections have a mechanical backstop beyond human review.

## Alternatives Considered
- A lighter-weight checklist for low-risk screens — rejected; the platform's enterprise/accessibility/multi-tenant requirements apply uniformly regardless of a screen's perceived complexity, and a shortcut here is exactly how compliance gaps accumulate over a 10-year product lifetime.

## Future Scalability
- This checklist's sections map closely to this document set's other 25 documents, so as any of those documents evolve, the corresponding checklist section is the natural place to reflect the change — keeping the checklist a living index into the design system rather than a static, drifting artifact.
