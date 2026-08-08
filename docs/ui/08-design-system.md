# 08 — Design System

## Purpose
Defines the enterprise design system's visual language, spacing/grid, elevation, radius, typography, color, motion, icons, illustrations, component strategy, and theming strategy — the foundation `09-design-tokens.md` implements as concrete token values.

## Visual Language
Calm, high-information-density-when-needed, low-chrome — benchmarked against Linear, Stripe Dashboard, Atlassian, GitHub, Vercel, Notion, Microsoft Fluent. Structure communicated through spacing and subtle borders/elevation, not heavy dividers or saturated color blocks. Color is reserved for meaning (status, action, alert) — never decoration. The Customer App is the one deliberate exception, using warmer accent tones and slightly larger, friendlier typography suited to a consumer context (`10-color-system.md`).

## Spacing & Grid
- **8px base spacing unit**, all spacing values are multiples of 4px (half-steps permitted for dense UI like Data Grid cell padding) — 4, 8, 12, 16, 24, 32, 48, 64.
- **12-column responsive grid** for Dashboard layouts, with defined gutter widths per breakpoint (`19-responsive-design.md`).
- Consistent page-level margins: 24px (desktop), 16px (tablet), 12px (mobile).

## Elevation
Four elevation levels, used sparingly and consistently:
| Level | Use |
|---|---|
| 0 | Flat surfaces, cards at rest |
| 1 | Raised cards, dropdown menus |
| 2 | Drawers, popovers |
| 3 | Modals, dialogs (highest interactive layer) |

Elevation is expressed via shadow tokens (`09-design-tokens.md`), never hardcoded per component.

## Radius
Three radius scales: sm (4px, inputs/badges), md (8px, cards/buttons), lg (12px, drawers/modals) — consistent rounding creates visual cohesion without needing per-component decisions.

## Typography
Full scale in `11-typography.md`; system font stack (native, fast-loading) for the Dashboard, matched by a comparable Flutter Material 3 type scale for mobile apps — no custom webfont dependency for Phase 1, prioritizing load performance over brand-specific type personality (revisitable in Future Scalability).

## Colors
Full semantic palette in `10-color-system.md`; never hardcoded — every color reference in code is a semantic token (`--color-text-primary`, not a raw hex value).

## Motion
Purposeful, restrained — communicates state change, never decoration (`01-product-principles.md`, `20-animation-guidelines.md`). Standard durations: 100ms (micro, hover/focus), 150ms (small transitions, toast), 250ms (drawer/modal open), 350ms (page-level transitions) — all respecting `prefers-reduced-motion`.

## Icons
- **Single icon set** across Dashboard and mobile apps for visual consistency: an outline-style icon library (24px default grid, 1.5px stroke weight), used identically in Angular and Flutter via platform-appropriate packages.
- Icons never carry meaning alone — always paired with a text label or accessible name, per the accessibility-first principle.

## Illustrations
A small, consistent illustration set for Empty/Error/Success states (`21-empty-error-success-states.md`) — flat, single-accent-color line illustrations (not photographic, not overly playful) matching the calm/professional visual language; consistent style across all three apps so a Customer seeing an empty state feels the same visual quality as staff on the Dashboard.

## Component Strategy
- **Shared-library-first**: every reusable component (`12-component-library.md`) is built once in a shared Angular library and once in a shared Flutter package, never duplicated per feature.
- **Composition over configuration sprawl**: components expose a small, deliberate set of variants/props (`13-component-specifications.md`) rather than accumulating one-off boolean flags per feature request.
- **Accessible by default**: every shared component ships with its accessibility behavior built in (focus management, ARIA, keyboard support) so feature teams inherit compliance rather than re-implementing it.

## Theme Strategy
Three themes — Light, Dark, High Contrast (WCAG 2.2 AA) — plus per-tenant branding (logo, primary color) layered on top of the base theme, never replacing it entirely (`22-theme-system.md`). Theme switching is instant (CSS custom property swap, no page reload) on the Dashboard; Flutter apps use theme-data swapping via Riverpod state.

## Best Practices
- No component, screen, or document in this system ever specifies a raw color/spacing/typography value — everything traces to a token (`09-design-tokens.md`).
- The design system is versioned and changes go through the same review discipline as code (Storybook visual regression, `13-component-specifications.md` Storybook Requirements).

## Risks
- Divergence between the Angular and Flutter implementations of the "same" design system is the highest ongoing risk for a cross-platform product — mitigated by defining every token in a platform-neutral JSON source (`09-design-tokens.md` §1) that both platforms consume, rather than maintaining two independently-authored token sets.

## Alternatives Considered
- A custom webfont/typeface — rejected for Phase 1 in favor of system fonts, prioritizing load performance and reducing a dependency; revisit if brand differentiation becomes a stronger business priority.
- Per-app independent design systems — rejected; a single token-driven system with app-specific tone adjustments (Customer App's warmth) preserves brand consistency while still fitting each context.

## Future Scalability
- The token-driven architecture means a future rebrand (new primary color, new typeface) is a token-file change, not a component-by-component rewrite — this is the single most important 10-year-maintainability decision in this design system.
