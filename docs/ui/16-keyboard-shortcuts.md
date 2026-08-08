# 16 — Keyboard Shortcuts

## Purpose
Designs the complete keyboard shortcut system for the Agency Web Dashboard — the platform's primary keyboard-first productivity surface (Dispatcher and Accountant personas especially, per `02-user-personas.md`).

## 1. Global Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+K (Cmd+K on macOS) | Open Command Palette |
| Ctrl+Shift+P | Open Command Palette in action-search mode (skips straight to actions, not navigation) |
| Ctrl+N | Create new record (context-aware: New Order on Order Queue, New Customer on Customer List) |
| Ctrl+S | Save current form (where applicable, prevents browser's native save-page behavior) |
| Ctrl+P | Print current document (Invoice, Report) |
| Forward slash | Focus the page's primary search/filter field |
| Esc | Close the topmost Drawer/Dialog, or clear the focused filter input |
| Ctrl+Shift+Question Mark | Open a shortcut cheat-sheet overlay listing all shortcuts available on the current screen |
| Alt+Left / Alt+Right | Navigate back/forward (browser-native, explicitly not overridden) |

## 2. Data Grid Navigation
Full detail in `14-data-grid-guidelines.md` section 9 — arrow keys, Home/End, Page Up/Down, Enter to open, Space to select, Ctrl+A to select all.

## 3. Dialog and Drawer Navigation
- Tab/Shift+Tab cycles within the dialog only (focus trap, `17-accessibility.md`).
- Esc closes (with dirty-state confirmation if applicable, `15-form-guidelines.md` section 6).
- Enter submits from the last logical field where the action is unambiguous (never from a multi-line textarea, to avoid accidental early submission).

## 4. Module-Specific Shortcuts

| Shortcut | Context | Action |
|---|---|---|
| A | Route Planning Board | Add selected order(s) to the current draft route |
| R | Complaint Queue, row focused | Resolve the focused complaint |
| E | Complaint Queue, row focused | Escalate the focused complaint |
| G then O | Global | Go to Orders |
| G then C | Global | Go to Customers |
| G then I | Global | Go to Inventory |
| G then R | Global | Go to Reports |

The G-then-X pattern (a two-key sequence) mirrors GitHub/Linear's navigation shortcut convention named in the design philosophy, keeping single-letter keys reserved for module-specific actions without collision.

## 5. Accessibility Shortcuts
- All shortcuts are discoverable: every actionable element with a shortcut shows it in its tooltip; the full list is always reachable via the cheat-sheet overlay (section 1).
- No shortcut uses a single unmodified letter key in a context where a text input might be focused (all single-letter shortcuts, section 4, are scoped to non-input-focused contexts) — prevents accidental triggering while typing.
- Shortcuts never override a screen reader's own navigation commands; all shortcuts are supplementary to, never a replacement for, standard assistive-technology navigation.
- Every shortcut has a mouse/touch equivalent — no action is keyboard-shortcut-only.

## Best Practices
- Shortcuts are learned passively via the Command Palette (`04-information-architecture.md` section 5), which always shows the shortcut for a matching action inline — reduces the need for upfront training.
- Shortcut assignments are centrally registered (a single shortcut-map service in the Angular app) to guarantee no two features accidentally claim the same key combination.

## Risks
- Shortcut collisions as new features are added — mitigated by the central registry (Best Practices above) which fails loudly (build-time or dev-time warning) on a duplicate binding.

## Alternatives Considered
- Fully user-customizable shortcuts — deferred; adds configuration complexity not justified for Phase 1 given the shortcut set is small and role-consistent; revisit if power users request it post-launch.

## Future Scalability
- The G-then-X navigation pattern scales cleanly to new Phase 2 modules (e.g. "G then B" for a future BI Dashboards module) without exhausting available single-key bindings.
