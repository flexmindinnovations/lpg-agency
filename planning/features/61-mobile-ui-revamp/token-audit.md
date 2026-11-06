# Token audit and theme engine notes (stories 1.1 to 1.3)

Audit date 2026-11-05, against the plan branch plus this change. Method: read `design-tokens/tokens.json`, `scripts/generate-tokens.mjs` output, `design_system/lib/src/*`, and grepped the design system and the three apps for colour, radius, spacing and duration literals and for translucency and blur.

## Where each kind of token lives
| Kind | Source of truth | Dart surface |
|---|---|---|
| Colour (primitive, semantic, light, dark, high contrast) | `design-tokens/tokens.json`, shared with the web dashboard | generated `tokens.dart`, read through `LpgColors` (`context.lpgColors`) |
| Type scale | `tokens.json` (`typography.*`) | `LpgTheme._textTheme`; letter spacing is the one Flutter-only addition |
| Spacing, sizes | `tokens.json` (`spacing.*`) | `LpgSpacing`, `LpgSizes` in `layout.dart` |
| Radius | `tokens.json` (`radius.*`, largest 12 px) | `LpgRadius`: card 18 px and hero or sheet 24 px are **derived in Dart** (1.5x and 2x the 12 px token), so `tokens.json` and the web build are untouched |
| Elevation | `tokens.json` stores CSS shadow strings, which the generator cannot turn into Dart | the same offsets and alphas are restated once, in `theme.dart` (`_lightCardShadow` and the others), and exposed per surface level by `LpgColors.shadowFor` |
| Motion | `tokens.json` (`motion.duration.*`, reduced-motion set) | `LpgMotion` (durations from tokens; springs and curves, shimmer and pulse are Flutter-only) |
| Surface layers, accent, density, text-scale limit | new, Flutter-only | `LpgSurfaceLevel`, `LpgAccent`, `LpgDensity`, `LpgThemeEngine` |

## Findings and what was done
**Already clean.** No colour literals (`Color(0x...)`) and no `BackdropFilter` anywhere in the three apps or the design system. The apps already used `LpgTheme.light/dark/highContrast` and built no `ThemeData` of their own.

**Translucent fills (fixed, 12 sites).** Tonal fills, the banner border, the hero watermark and muted hero text, the hero progress track, the order-tracking and stop-map floating cards (94 and 95 percent opaque), the KYC overlay and the unread-notification highlight in three apps were alpha-blended on screen. They are now **solid colours**: `LpgColors.tint` blends once to an opaque colour, and the hero tiers (`heroMuted`, `heroSubtle`, `heroTrack`) are named tokens. A test now scans the design system and the three apps and fails on any `BackdropFilter`, `ImageFilter.blur` or alpha-blended fill outside an allow-list: `theme.dart` (shadows, the blend helper), `lpg_splash.dart` and `lpg_timeline.dart` (animated brand effects, not surfaces).

**Muted hero text (fixed).** Secondary text on the hero gradient measured 3.97:1 on the light end of the light theme (under the 4.5:1 AA floor); it is now 92 percent white, solid, and a test pins 4.5:1 across the whole gradient in all three variants.

**Surfaces (new).** Four solid layers (canvas, card, sheet, inverse) with fill, 1 px hairline and shadow from one place (`LpgSurface`, `LpgColors.surfaceFor/shadowFor/hairlineFor`). Dialogs, bottom sheets and menus now use the sheet layer (white on light, one tonal step above cards on dark) and snackbars the inverse layer (so dark mode gets a light snackbar rather than a card-coloured one). **This is the one visible change in dark mode**; light mode is unchanged.

**Literals left on purpose (recorded, not fixed).**
- `Colors.white` behind the UPI QR (a QR needs a white quiet zone); `Colors.black` shadow and `Colors.white` glints in the splash animation.
- Layout constants in the Admin app: a 420 px list pane (`order_list_screen.dart`), a 120 px proof-image preview, two `SizedBox(height: 2)` gaps (`metric_tile.dart`, `customer_detail_screen.dart`). Move them to named layout tokens during the Admin rollout (E9).
- Input debounce durations (300 to 350 ms, five Admin screens) are not motion; give them one named constant in the Admin rollout.
- Radii above the 16 to 20 px band in the direction note: heroes, sheets and dialogs are 24 px, inputs and buttons 12 px. Kept: large floating surfaces read better rounder, and the note's band is for cards (18 px).

**Contrast gaps found, not fixed (decision needed).** In the light theme, status tone colours used as text on their own tinted container are under 4.5:1: accent 2.8, success 2.9, warning 2.8, danger 4.0, info 4.4, neutral 4.4 (dark and high contrast pass). They come from the shared web tokens (`green.600`, `amber.600`, `flameOrange.500`), so darkening them also changes the web dashboard. A test pins the current list so it can only shrink. Decide in story 10.1 (accessibility audit): darken the shared tokens, or use a darker text-only shade on mobile.

## Behaviour of the engine in the three apps
`LpgThemeEngine()` (default accent: flame orange, so today's colours) replaces direct `LpgTheme.*` use in each `main.dart`.
- Same themes as before, plus text scale limited to 2.0x and the density extension (phone values equal today's spacing; nothing reads it yet, screens move to it in E6).
- One deliberate difference: **Admin now also passes the high-contrast theme for dark mode** (Customer and Driver already did), so a dark-mode user with high contrast on gets high contrast in Admin too.
- Reduce motion: the platform setting already collapsed component animations; it now also makes page transitions instant, and `LpgThemeEngine(reduceMotion: true)` forces it.
