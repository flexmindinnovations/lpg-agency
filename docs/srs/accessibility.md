# Accessibility Requirements

## 1. Source Coverage
Accessibility is **not mentioned anywhere in the original blueprint PDF.** All requirements in this document originate from the extended project instructions, which explicitly mandate WCAG 2.2 AA compliance. This is called out clearly because it represents a significant scope addition beyond the original blueprint and should be acknowledged as such in planning/estimation.

## 2. Standard
- The Agency Web Dashboard (and, where applicable, the mobile apps' accessible-equivalent standards, e.g., platform accessibility APIs) shall conform to **WCAG 2.2 Level AA.**

## 3. Required Capabilities
- **Keyboard Navigation**: All interactive elements (buttons, forms, tables, dialogs) must be operable via keyboard alone.
- **Tab Order**: Logical, predictable tab order matching visual layout.
- **Skip Links**: "Skip to main content" style links for screen-reader and keyboard users.
- **Focus Management**: Visible focus indicators; focus must be programmatically managed when dialogs/drawers open and close (e.g., focus trapped in modal, returned to trigger element on close).
- **Screen Reader Support**: All content must be perceivable via screen readers (NVDA/JAWS/VoiceOver-class tools).
- **ARIA Labels**: Proper semantic roles and ARIA attributes on custom components (data grid, dropdowns, steppers, tabs, etc.).
- **High Contrast Mode**: A dedicated High Contrast theme (ties to `requirements/non-functional.md` §5 design token system).
- **Reduced Motion**: Respect user "prefers-reduced-motion" settings; avoid essential information conveyed only through animation.
- **Color Contrast**: All text/background combinations must meet WCAG AA contrast ratios (4.5:1 normal text, 3:1 large text) across Light, Dark, and High Contrast themes.
- **Semantic HTML**: Use of proper HTML5 semantic elements rather than generic divs for structural/interactive content.
- **Accessible Forms**: Labels programmatically associated with inputs, clear error identification and suggestions, no reliance on color alone to indicate validation state.
- **Accessible Dialogs**: Proper modal semantics (role="dialog", aria-modal, labeled by heading).
- **Accessible Tables**: Proper table headers/scope attributes, especially important given the heavy use of Enterprise Data Grids across Order, Inventory, and Reporting modules.

## 4. Scope Application
These requirements apply primarily to the **Agency Web Dashboard**, which carries the most complex UI (data grids, forms, dialogs). The Customer and Driver mobile apps should follow platform-native accessibility guidelines (e.g., Android/iOS accessibility APIs via Flutter's accessibility support), though this is not explicitly detailed in either source document.

## 5. Testing & Validation (Recommended, Not Explicit)
- Automated accessibility testing (e.g., axe-core or equivalent) integrated into CI/CD.
- Manual screen-reader testing for key flows (booking, order approval, invoice generation) prior to release.

## 6. Timing — CONFIRMED (D-35)
WCAG 2.2 AA compliance is **confirmed as a Phase 1 launch requirement**, not a deferred/longer-term target. This has direct cost/schedule impact and should be reflected in Phase 3 (UI/UX Design) and Phase 7 (Testing) planning and estimation.
