# 64 - Frosted glass chrome (web dashboard and mobile apps)

**Request (owner, 2026-11-17):** a frosted-glass background blur, in the style of One UI / iOS materials, on top of the existing paper grain. Chrome only. The light/dark theme system and the paper texture are not changed.

## Surfaces
- **Web:** shell header, sidebar, dialogs, drawers, toasts.
- **Mobile (Flutter, shared `design_system`, so admin, customer and driver):** bottom navigation bar, frosted sheets.
- Never cards, list rows, table rows or fields.

## Design
Layer order on every glass surface: page paper, glass (backdrop blur + theme tint), grain, content.
- **Tokens** are added beside the existing theme tokens: `--glass-*` in `tokens.css` (all four theme selectors), and `LpgGlassTokens` (derived from the theme's own colours, like `LpgBackdropLook`) on mobile. Tints derive from the surface tokens; bar and sheet tint opacity stay the contrast-derived `LpgGlassLook` values on mobile.
- **Web grain:** the page grain is one fixed layer (`body::after`, z 900) that is already above the header and sidebar, so those carry no second grain. Surfaces above it (dialogs, drawers: existing `::after`; toasts and `.glass--grain`: new, same tile, `--glass-grain-*`) carry their own.
- **Fallback:** the base `.glass` rule is the nearly solid fallback tint; blur is added inside `@supports`, and `prefers-reduced-transparency` and print drop it. Mobile: `LpgGlassPolicy.blur` off or high contrast gives the same tint (more opaque) and grain.
- Blur is never animated or transitioned; surfaces move/fade with transform and opacity only.

## Out of scope / recorded
- Toasts (SnackBar) and the scrolled header on mobile; a frame-time monitor that flips `LpgGlassPolicy.blur` automatically; saturation boost on mobile (Flutter has no backdrop colour-matrix filter); real-device FPS, Safari and low-end Android measurements.
