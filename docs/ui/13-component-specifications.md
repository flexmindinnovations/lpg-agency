# 13 — Component Specifications

## Purpose
For every component category, defines purpose, variants, states, properties, accessibility, keyboard support, validation, animations, responsive behavior, Storybook requirements, and design tokens used.

## Scope and Approach
Following the same pattern as `07-wireframe-specifications.md`, this document defines the specification template every component must satisfy, then provides full worked specifications for a representative component per category (the ones most load-bearing across the platform). Every other cataloged component (`12-component-library.md`) is specified using this same template structure at implementation time, and every such spec is reviewed against `26-design-review-checklist.md` before merge.

## Specification Template (Required Fields for Every Component)
Purpose, Variants, States (default, hover, focus, active, disabled, loading, error), Properties (inputs and outputs), Accessibility (role, ARIA, labeling), Keyboard Support, Validation (if applicable), Animations, Responsive Behavior, Storybook Requirements (all variants times states documented as stories), Design Tokens Used.

---

## Worked Spec 1 — Button

**Purpose:** The primary interactive trigger for actions across the platform.
**Variants:** Primary, Secondary, Tertiary (text-only), Destructive, Icon-only.
**States:** Default, Hover, Focus-visible, Active/Pressed, Disabled, Loading (inline spinner replaces label, button width preserved to avoid layout shift).
**Properties:** label, variant, size (sm/md/lg), icon (optional, leading or trailing), disabled, loading, onClick.
**Accessibility:** Native button element (never a styled div); aria-busy true while loading; icon-only variant requires an accessible label.
**Keyboard Support:** Focusable via Tab; activates on Enter and Space; focus-visible ring uses the primary action color at 3:1+ contrast.
**Validation:** N/A (not a form input).
**Animations:** Background-color transition on hover/active (100ms, micro duration token); loading spinner uses the standard Spinner component's rotation animation, exempted from prefers-reduced-motion since a stopped-but-still-loading spinner would be actively misleading (a documented, deliberate exception).
**Responsive Behavior:** Small size used in dense contexts (Data Grid row actions), medium default, large reserved for primary CTAs on Customer App screens.
**Storybook Requirements:** All variant times size times state combinations as individual stories, plus an accessibility-addon-validated story confirming contrast and focus order.
**Design Tokens Used:** button.primary component tokens, motion.duration.micro.

---

## Worked Spec 2 — Data Grid

**Purpose:** The platform's primary mechanism for browsing, filtering, and acting on lists of records — full behavioral detail in `14-data-grid-guidelines.md`; this entry specifies its component-level contract.
**Variants:** Standard (full-featured), Compact (dense rows, used in Drawer-embedded lists, e.g. an Order's line items).
**States:** Loading (skeleton rows), Empty, Error, Populated, Row-selected, Row-focused.
**Properties:** columns (definition array), rows (data), sortModel, filterModel, selectionMode (none/single/multi), onRowClick, pageSize.
**Accessibility:** Grid role with row and gridcell roles on children, aria-sort on sortable column headers, row/column count attributes for screen-reader context on virtualized grids.
**Keyboard Support:** Full arrow-key cell/row navigation, Home/End, Page Up/Down, Enter to open a row, Space to toggle selection — full detail `14-data-grid-guidelines.md` section 9.
**Validation:** N/A.
**Animations:** Row insertion/removal (e.g. after a filter change) animates with a 150ms fade, never a jarring instant swap, so the user's eye can track what changed.
**Responsive Behavior:** Converts to a card-list pattern below the tablet breakpoint (`14-data-grid-guidelines.md` section 11).
**Storybook Requirements:** Stories for each state, plus a dedicated accessibility story exercising keyboard navigation.
**Design Tokens Used:** dataGrid component tokens, elevation level 1 (sticky header shadow on scroll).

---

## Worked Spec 3 — Dialog and Drawer

**Purpose:** Focused, modal contexts for actions that should not navigate away from the underlying screen (forms, confirmations).
**Variants:** Dialog (centered, for confirmations and short forms), Drawer (right-slide, for longer forms — the Action Screen template in `07-wireframe-specifications.md`).
**States:** Opening (enter transition), Open, Closing (exit transition).
**Properties:** title, size, isOpen, onClose, preventCloseOnOutsideClick (used for in-progress destructive flows only).
**Accessibility:** Dialog role with aria-modal true, labeled via a reference to the title element; focus is trapped within while open and returned to the triggering element on close (`17-accessibility.md`).
**Keyboard Support:** Esc closes (with dirty-state confirmation if applicable); Tab cycles only within the dialog's focusable elements.
**Validation:** N/A (delegated to contained form).
**Animations:** Drawer slides in from the right (250ms, medium duration token); Dialog fades and scales slightly (98 percent to 100 percent) on open; both respect prefers-reduced-motion (instant show/hide with only an opacity fade at a shortened duration).
**Responsive Behavior:** Drawer becomes full-screen below the tablet breakpoint.
**Storybook Requirements:** Dialog and Drawer variants, each with a focus-trap-verified interaction test.
**Design Tokens Used:** elevation level 3, z-index modal/drawer tokens, radius large.

---

## Worked Spec 4 — Signature Pad (Domain-Specific, Driver App)

**Purpose:** Captures a customer's signature as part of Proof of Delivery (BR-08, BR-23).
**Variants:** Single variant (no visual variants — this is a functional capture component).
**States:** Empty (awaiting first stroke), Drawing, Captured (with a Clear affordance), Error (capture failed to save locally).
**Properties:** onCapture (returns an image blob reference), minStrokeCount (rejects an accidental single-tap signature).
**Accessibility:** Since a signature is inherently a visual/motor capture that has no meaningful non-visual equivalent, the surrounding screen provides an alternative acknowledgment path — a checkbox alternative is explicitly not provided, since it would undermine BR-23's proof requirement. Accessibility here focuses on ensuring the capture canvas has adequate touch-target size and clear visual state, and that surrounding instructional text is fully screen-reader accessible even though the canvas interaction itself is inherently touch/stylus-based.
**Keyboard Support:** N/A (touch/stylus-primary component); the Clear and Confirm actions flanking the canvas are fully keyboard-operable for the rare external-keyboard-connected device.
**Validation:** Rejects capture with fewer than minStrokeCount points (prevents accidental blank/near-blank signatures).
**Animations:** None beyond the stroke rendering itself (must feel instant, zero input lag).
**Responsive Behavior:** Canvas sizes to at least 300x120dp minimum on the smallest supported device, scaling up on larger screens.
**Storybook Requirements:** N/A for this component on the Angular side (Flutter-only component); Flutter widget tests cover Empty/Drawing/Captured/Error states.
**Design Tokens Used:** color-border-default (canvas border), radius medium.

## Best Practices
- Every component's Storybook stories double as the primary visual regression test surface — a component isn't considered complete until every state listed in its spec has a corresponding story.
- Domain-specific components (Worked Spec 4) still document accessibility even when the interaction is inherently non-keyboard, so the decision not to force an artificial keyboard path is documented, not silently absent.

## Risks
- Components not individually worked-out here risk under-specified accessibility/keyboard behavior — mitigated by the mandatory template (all fields required, no field optional) applied at implementation time, reviewed via `26-design-review-checklist.md`.

## Alternatives Considered
- Skipping formal specification for simple components (e.g. Divider, Spacer) — rejected; even trivial components get a minimal template pass (most fields N/A) to keep the specification process uniform and prevent silent scope gaps.

## Future Scalability
- The template's stability (same fields for every component, forever) means a component library audit tool could, in the future, mechanically verify every component's documentation completeness against this template.
