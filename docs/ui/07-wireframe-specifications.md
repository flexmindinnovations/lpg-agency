# 07 — Wireframe Specifications

## Purpose
Defines, for every screen state (loading, empty, error, success), the layout, widgets, actions, responsive behavior, keyboard behavior, and accessibility requirements — detailed enough for direct implementation.

## Scope & Approach
Given the platform's 61-screen inventory (`05-screen-inventory.md`), this document establishes **three reusable screen templates** (List, Detail, Action) that every screen of that shape must conform to, then provides **full, screen-specific specifications** for every screen whose behavior deviates meaningfully from its template (the higher-complexity L/XL screens, plus one worked example per template so implementers have a concrete reference). Screens not individually detailed below inherit their template's specification exactly, with only their module-specific data/actions substituted per `05-screen-inventory.md`'s columns — this keeps the specification complete without 61 near-duplicate documents.

---

## Template A — List/Queue Screen
*(Applies to: Order Queue, Customer List, Invoice List, Complaint Queue, Stock Overview, and all other Data Grid-based list screens.)*

**Layout:** Page header (title + primary action button) → Filter bar → Data Grid (full detail: `14-data-grid-guidelines.md`) → Pagination footer.
**Widgets:** Data Grid, Filter chips, Column chooser, Bulk action bar (appears on row selection).
**Primary Actions:** Create new record (button, top-right); row click opens Detail.
**Secondary Actions:** Export, bulk actions (on selection), saved-view management.
**Loading State:** Skeleton rows (5–8 placeholder rows matching the grid's column structure) — never a spinner-only blank screen, since skeleton rows preserve layout stability.
**Empty State:** Illustration + message + primary CTA (e.g., "No orders yet — create your first order") — see `21-empty-error-success-states.md` §1.
**Error State:** Inline banner above the grid ("Couldn't load orders — Retry") — grid area shows a retry-focused empty state, not a full-page error.
**Success State:** N/A at list level (success is implicit in showing data); row-level success (e.g., after bulk action) shows a toast.
**Responsive Behavior:** Desktop/tablet = full grid; mobile = card-list conversion (`14-data-grid-guidelines.md` §11).
**Keyboard Behavior:** Arrow keys navigate rows, Enter opens Detail, Space toggles row selection, `/` focuses the filter search field.
**Accessibility:** Grid uses `role="grid"` semantics, `aria-sort` on sortable headers, filter inputs properly labeled, bulk-action bar announced via `aria-live="polite"` on selection count change.

---

## Template B — Detail Screen
*(Applies to: Order Detail, Customer Detail, Invoice Detail, Complaint Detail.)*

**Layout:** Breadcrumb → Header (record identifier + status badge + primary action) → Tabbed or sectioned content (Overview, related-record links, History/Audit).
**Widgets:** Status badge, key-value summary panel, related-record link cards, activity timeline (`12-component-library.md`).
**Primary Actions:** The single next valid state-machine action (e.g., "Cancel Order," "Resolve Complaint") — computed from the record's current status, never showing an action that would be rejected by the state machine (`docs/data/08-state-machines.md`).
**Secondary Actions:** Print (where applicable), edit (where the domain model allows), view audit history.
**Loading State:** Skeleton header + skeleton content blocks matching the eventual layout.
**Empty State:** N/A (a Detail screen always has a record by definition; a missing-record case is the Error State).
**Error State:** Full-page "Not Found" or "Access Denied" pattern (`21-empty-error-success-states.md` §4–5), since a Detail screen without its record has nothing else useful to show.
**Success State:** Inline confirmation (toast) after any action; status badge updates immediately (optimistic UI where the action is low-risk, confirmed-then-updated where destructive).
**Responsive Behavior:** Desktop = two-column (summary panel + main content); tablet/mobile = single column, tabs become an accordion.
**Keyboard Behavior:** Tab order follows visual hierarchy; primary action reachable via a consistent shortcut where defined (`16-keyboard-shortcuts.md`).
**Accessibility:** Status changes announced via `aria-live`; tabs use proper `role="tablist"`/`role="tab"` semantics.

---

## Template C — Action Screen (Drawer/Dialog)
*(Applies to: New/Edit Customer, GRN Entry, Payment Recording, Credit Note Request, Inventory Adjustment.)*

**Layout:** Drawer sliding from the right (desktop/tablet) or full-screen modal (mobile) — Header (title + close) → Form body → Footer (Cancel + Primary Submit button).
**Widgets:** Form fields per `15-form-guidelines.md`, inline validation messages.
**Primary Actions:** Submit/Save.
**Secondary Actions:** Cancel/Close (confirms if the form is dirty, per `15-form-guidelines.md` §7).
**Loading State:** Submit button shows an inline spinner + disables during submission; form fields disabled during submission.
**Empty State:** N/A (a form's initial state is its empty/default state, not a distinct pattern).
**Error State:** Server-validation errors shown inline per-field (`15-form-guidelines.md` §8) plus a summary banner at the top of the form if multiple fields fail.
**Success State:** Drawer closes, toast confirms, and (for create actions) the new record is highlighted/scrolled-to in the underlying List screen.
**Responsive Behavior:** Drawer width fixed on desktop (480px), full-width on tablet, full-screen on mobile.
**Keyboard Behavior:** Focus trapped within the Drawer/Dialog while open (`17-accessibility.md`); Esc closes (with dirty-state confirmation); Enter submits from the last field where unambiguous.
**Accessibility:** `role="dialog"`, `aria-modal="true"`, labeled by its header; focus returns to the triggering element on close.

---

## Worked Example 1 — D-08 Route Planning Board (XL, Deviates Significantly from Templates)

**Purpose:** Let a Dispatcher build one or more Routes from the day's Pending/Confirmed orders, assigning driver + vehicle, with live capacity feedback.
**Layout:** Three-panel: left = unassigned Orders list (filterable by branch/date), center = Route builder (drag target, or multi-select + "Add to Route" button as the keyboard-accessible equivalent), right = Driver/Vehicle assignment panel with live stock-sufficiency indicator (BR-09).
**Widgets:** Draggable order cards, drop-zone route panel, capacity gauge (visual: fill level for the selected vehicle's stock vs. route demand), driver/vehicle selector dropdowns.
**Primary Actions:** "Create Route" (commits the current draft), "Assign Driver & Vehicle."
**Secondary Actions:** Remove an order from a draft route, split a route, save as draft without committing.
**Loading State:** Skeleton for both the unassigned-orders list and any existing routes for the selected date.
**Empty State:** "No pending orders for this date" in the left panel.
**Error State:** If a route commit fails (e.g., a race condition where an order was cancelled mid-planning), the specific order card shows an inline error and is returned to the unassigned list — the rest of the route commit is unaffected.
**Success State:** Route appears in a "Today's Routes" summary strip at the top of the screen; toast confirms.
**Responsive Behavior:** This screen is desktop/tablet-primary (Dispatcher persona works at a desk) — on mobile, it degrades to a simplified sequential flow (select orders, select driver/vehicle, create) rather than the three-panel layout, since drag-and-drop route building isn't a realistic mobile interaction.
**Keyboard Behavior:** Every drag-and-drop action has a keyboard equivalent: select an order card (Space), then a "move to route" command (via Command Palette or a visible "Add to Route" button) — drag-and-drop is a convenience layer over a fully keyboard-operable action set, never the only way to perform the action.
**Accessibility:** Live region announces capacity changes ("Vehicle now at 45 of 60 units") as orders are added/removed from the draft route.

## Worked Example 2 — DR-05 Delivery Confirmation (Driver App, Offline-Critical)

**Purpose:** Capture BR-08/BR-23's complete Proof of Delivery (OTP + signature + photo + GPS) and record delivered/collected quantities, working fully offline.
**Layout:** Single-column, large-touch-target sequence: Quantity confirmation → OTP entry → Signature capture → Photo capture → Confirm.
**Widgets:** Numeric steppers (not free-text) for quantities, OTP input (6-digit, large digits), Signature Pad (`12-component-library.md`), camera capture button.
**Primary Actions:** "Confirm Delivery" (final step, only enabled once all four POD elements are captured).
**Secondary Actions:** "Report an Issue" (routes to Failed Delivery, DR-07) accessible at any point in the sequence.
**Loading State:** N/A for capture steps (all local/offline); a subtle "queued for sync" indicator appears immediately after Confirm, never a blocking spinner (per D-24, the action must feel instant regardless of connectivity).
**Empty State:** N/A.
**Error State:** OTP mismatch shows inline, non-blocking retry (doesn't lose the already-captured signature/photo); a GPS-unavailable state offers a manual retry with clear messaging, never silently proceeding without coordinates.
**Success State:** Full-screen confirmation ("Delivered!") with a brief animation, then auto-advances to the next stop or Route Summary if this was the last stop.
**Responsive Behavior:** Mobile-only screen (Driver App); large touch targets (minimum 48×48dp) throughout given the outdoor/gloved/one-handed usage context (`02-user-personas.md` Driver persona).
**Keyboard Behavior:** N/A (touch-primary mobile context); external keyboard support not a Phase 1 requirement for this screen.
**Accessibility:** High contrast mode support essential given outdoor/sunlight use; all icons paired with text labels (never icon-only) since the Driver persona skews lower on tech comfort.

## Best Practices
- Every screen not individually detailed above must be implemented as a strict instance of its Template (A/B/C) — any deviation from the template requires a documented reason, following the pattern of the two worked examples.
- Screen specs are the direct input to `25-lovable-prompts.md` — every field in this document (loading/empty/error/success states, keyboard behavior, accessibility) maps to a required section in each screen's Lovable prompt.

## Risks
- Template-based coverage risks under-specifying a screen with genuinely unique needs that wasn't flagged as a "worked example" — mitigated by requiring designers to explicitly confirm template conformance (not just assume it) during the design review (`26-design-review-checklist.md`).

## Future Scalability
- New screens are designed by first asking "which template does this fit" before considering a bespoke layout — keeping the platform's screen count from fragmenting into inconsistent one-off patterns over a 10-year maintenance horizon.
