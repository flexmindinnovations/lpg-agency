# 15 — Form Guidelines

## Purpose
Designs enterprise form patterns: validation, wizard forms, autosave, undo/redo, dependent fields, dirty state, inline errors, server validation, accessibility.

## 1. Validation Timing
- Field-level validation runs on blur (not on every keystroke, which is distracting) except for fields with an inherently fast-feedback need (e.g. password strength meter, character-count-limited fields), which validate on change.
- Full-form validation runs on submit attempt; any invalid field is scrolled into view and focused automatically.
- Shape validation (required, format, length) is instant/client-side; business-rule validation (e.g. BR-19 credit limit) only resolves after the server round-trip on submit — the form clearly distinguishes "this field is malformed" (immediate) from "this action isn't currently allowed" (post-submit), matching the two-tier error model in `docs/data/13-validation-rules.md` section 1.

## 2. Wizard Forms
Used only where a form's fields have genuine sequential dependency or the field count is large enough that a single page would overwhelm (e.g. a future Tenant Onboarding flow) — most platform forms (New Customer, GRN Entry) are single-page, since the Dispatcher/Warehouse Staff personas move faster with everything visible at once.
- Wizard steps show a Stepper component indicating progress, with the ability to navigate back to a completed step without losing entered data.
- Each step validates before allowing Next; the final step's submit triggers full-form plus business-rule validation.

## 3. Autosave
Applied to longer-lived, draft-capable forms (primarily the Order Draft state in the Customer App, matching the Order state machine's explicit Draft status, `docs/data/08-state-machines.md` section 2) — the form silently persists to local/server draft state every few seconds of inactivity, with a subtle Saved indicator, never interrupting the user with a save dialog.
- Not applied to short, single-action forms (Payment Recording, GRN Entry) where autosave would add complexity without real benefit — these submit explicitly.

## 4. Undo and Redo
- For destructive-but-recoverable actions within a form session (e.g. clearing a multi-line Order's line items), a brief Undo toast appears after the clearing action rather than a confirmation dialog before it — reduces friction for the common case while still protecting against mistakes, consistent with Product Principle 5 (forgiving by default).
- Full document-level undo/redo is supported within Drawer-based forms for field-value changes during the current editing session, not persisted across sessions.

## 5. Dependent Fields
- Fields that depend on another field's value (e.g. Cylinder Type options filtered by the customer's Branch/Warehouse availability) update reactively and clear/reset if their controlling field changes in a way that invalidates the current selection — always with a visible, non-jarring transition (fade plus height animation), never an instant field disappearance.
- Dependent-field logic is documented per form at implementation time; the general pattern (react to controlling field, clear on invalidation, animate the change) is the platform-wide standard.

## 6. Dirty State
- Any form with unsaved changes tracks a dirty flag; navigating away (closing a Drawer, clicking a different Sidebar item) triggers a confirmation (Discard unsaved changes) only if the form is dirty — a clean/untouched form closes silently.
- The dirty-state confirmation is a lightweight inline Dialog, not a full-page interruption.

## 7. Inline Errors
- Field-level errors appear directly below the field, in the danger status color, paired with an error icon (never color alone) and concise, actionable text (e.g. "Phone number must be 10 digits," not "Invalid input").
- A form-level error summary banner appears above the form only when submit fails with multiple field errors, listing each with a jump-to-field link — supports the accessibility requirement that a screen-reader user gets a single, navigable summary rather than having to tab through the whole form to discover every error.

## 8. Server Validation
- Server-side business-rule validation errors (`docs/data/18-error-catalog.md`) map to either a specific field (if the error is field-attributable, e.g. duplicate phone) or a form-level banner (if not field-specific, e.g. credit limit exceeded) — the mapping between error code and field/banner placement is a documented, explicit table per form at implementation time, never a generic "something went wrong."
- Server validation errors never silently clear entered data — the user's input remains in the form for correction.

## 9. Accessibility
- Every field has a programmatically associated label (never placeholder-text-as-label).
- Required fields are indicated both visually (asterisk plus color) and via the required attribute/ARIA equivalent, not visually alone.
- Error messages are associated with their field and announced via a live region when they first appear.
- Focus order follows visual/logical order; the first invalid field receives focus automatically on failed submit.

## Best Practices
- Every form in the platform uses the same validation-timing, error-display, and dirty-state patterns — a user who has used one Dashboard form already knows how every other form behaves.
- Numeric fields (quantities, amounts) use appropriate input modes (numeric keyboard on mobile, stepper controls where the Warehouse Staff/Driver persona benefits from fewer typing errors).

## Risks
- Autosave applied inconsistently across forms could confuse users about which forms are safe to walk away from — mitigated by a consistent visual indicator (a small "Draft saved" label) present only on autosaving forms, absent elsewhere.

## Alternatives Considered
- Validate-on-every-keystroke for all fields — rejected as distracting/noisy for most fields; reserved only for fields with a genuine fast-feedback need.
- Full autosave on every form — rejected; adds unnecessary complexity to simple, fast, single-action forms where explicit submit is both simpler to implement and clearer to the user.

## Future Scalability
- The dependent-field pattern and wizard-form infrastructure are designed to support a future Tenant Onboarding wizard (referenced in `docs/data/19-data-migration.md`) without new form-pattern invention.
