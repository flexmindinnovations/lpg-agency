# Design direction: modern, solid, enterprise (story 0.1)

Applies to the Admin, Customer and Driver apps. Input to epics E1 (theme engine) and E4 (component library). Decisions already made by the owner: **no glass, no blur, no transparency** (amended by the owner in story 5.11: glass is now allowed in the limited, contrast-sized form described at the end of this file); one theme engine; high-contrast mode; WCAG 2.2 AA.

## What exists today (read from the code, 2026-11-05)
- One token source, `design-tokens/tokens.json`, is **shared with the Angular dashboard**: it generates both the web CSS and `design_system/lib/src/tokens.dart`. Anything added there reaches the web's generated output, so mobile-only additions must stay out of the web build (decided in story 1.1, without touching the Angular source).
- Brand: deep **gas blue** (`gasBlue.800`) as the structural colour, **flame orange** as the accent, Inter bundled as the typeface. Light, dark and high-contrast variants already exist (`LpgTheme`); high contrast replaces shadows with thick borders.
- Radius tokens stop at 12 px (`full` for pills); shadows exist as card and floating levels; motion has four durations and a reduced-motion set.
- The three apps already pass `LpgTheme.light/dark/highContrast` to `MaterialApp` and do not build their own `ThemeData`; the engine formalises that and adds accent, density and text-scale rules.

## The look in one paragraph
Calm, **solid** surfaces. Depth comes from **tonal elevation** (each level a slightly different solid surface tone) plus **soft shadows** and **1 px hairlines**, never from transparency. **16 to 20 px radii** on cards and sheets, pills for chips. Generous spacing on the existing scale. Numbers are the heroes: stat cards use large bold figures. One strong brand accent per app, semantic colours reserved for status, and every status also carries an icon or label.

## Rules

**Surfaces and elevation** (no `BackdropFilter`, no alpha-blended fills for surfaces)
- Five solid layers: canvas, card, raised, overlay (sheets and menus), and inverse (hero, snackbars). Light mode steps by tone and shadow; dark mode steps by lighter tone and relies little on shadow; high contrast uses a 2 px border and no shadow.
- Cards: 16 px radius, hairline border (`borderDefault`), soft shadow in light mode only. Sheets and dialogs: 20 px top or all-round radius.
- A hairline is always 1 px (`borderWidth.thin`), never a thinner or translucent line.

**Colour**
- Structural colour stays gas blue; each app picks one **accent** seed through the theme engine (proposed: Admin keeps blue, Customer uses flame orange for its primary action, Driver uses flame orange with larger controls). Owner may change; the engine takes it as one parameter.
- Status colours (success, warning, danger, info) are fixed across apps and never used decoratively.
- Text on solid surfaces meets 4.5:1 (3:1 for 18 sp bold and above and for icons and borders that carry meaning). Secondary text may not go lighter than the current `textSecondary`. Never rely on colour alone.

**Type scale** (Inter; scale and weights live in tokens, not in screens)
- Roles: display (hero figures), headline, title, body, label, caption. Body is at least 14 sp; the Driver app's primary text is 16 sp or larger because it is read outdoors at arm's length.
- Figures in tables and stat cards use tabular numerals and a heavier weight. Amounts always show the rupee sign and Indian grouping.
- Text scale is honoured up to 1.3x on dense screens (lists, tables) and 2.0x elsewhere, where layouts reflow rather than clip; the engine owns the clamp.
- Hindi and Marathi run 30 to 40 percent longer: no fixed-width labels, no text baked into images.

**Shape and touch**
- Touch targets at least 48 x 48 dp (WCAG 2.2 asks 24 px minimum; our rule is stricter), with at least 8 dp between neighbours.
- Focus is always visible: a 2 px ring in `borderFocus`, offset from the control, in every theme variant.

**Motion**
- Purposeful, short, and always with a reduced-motion version: shared-axis page transitions, count-up on figures, press feedback, skeleton shimmer. Durations come from the motion tokens (100, 150, 250, 350 ms). With reduced motion on, transitions are near-instant and shimmer becomes a static placeholder.
- Nothing animates for decoration only; no looping animation on a screen the person is reading.

**Density and tablets**
- Three size classes (compact, medium, expanded) drive density: spacing and row height step up one notch on expanded; content width is capped on tablets; navigation moves from bar to rail to sidebar (epic E6).

**Accessibility baseline (WCAG 2.2 AA, a Phase 1 requirement)**
- Contrast as above; labels and semantics on every interactive element; error text next to the field, never colour only; screen reader order matches visual order; dynamic type and reduced motion respected; high-contrast mode tested on every new component.
- **Readable in direct sunlight for drivers**: solid high-contrast surfaces, no pale-grey on white for anything actionable, large primary buttons.

## Reference screens (the pattern each app is built to)
| App | Reference screen | What it demonstrates |
|---|---|---|
| Admin | Dashboard | Hero stat card with the day's bookings, attention list, metric grid, live trips; tablet multi-column |
| Customer | Home | Cylinder balance hero, one primary action (order a refill), live order card, recent orders |
| Driver | Today | Route hero with progress, next-stop card with a large primary action, cash in hand, live location switch |

These three screens are converted first in epics E3 (async states) and E9, E7, E8 (rollout), and become the pattern for the rest.

## Not decided here
Final accent per app (proposal above), custom domain icons and illustrations (E5), component specifications (E4), motion kit details (E4.4).

## Illustrated stat cards (pilot, story 5.5)
A stat card may carry one flat illustration behind its figure, drawn in the card's own tone. It stays inside the no-transparency rule: every layer is an opaque tint (`LpgColors.tint`), the largest shapes the faintest. Rules that keep it safe:
- **Text colour.** Secondary text only just clears 4.5:1 on a plain card, so a tile with a picture uses the primary text colour for its label and caption. The strongest layer must keep primary text at 4.5:1 for every tone in every theme (a test holds this).
- **Motion.** The picture settles in once and breathes three times, then rests, so a screen of them is lively when it opens and still afterwards. Reduce-motion draws the finished picture and never moves it. High contrast draws nothing.
- **Paper page (5.8).** The one place a soft, blurred background is allowed: the page behind every screen, never a surface. Strength is whatever keeps secondary text at 4.5:1 on the worst pixel; `LpgBackdropLook` computes it.
- **Files, not code.** Each picture is an SVG in `design_system/assets/illustrations/`, drawn in four placeholder greys that the widget recolours to the tile's tone (see that folder's README for the rules). Never put markup or path data in Dart.
- **Decorative only.** Excluded from semantics and touches; the tile reads and behaves the same with or without it, and its content does not move.

## Glass (5.11, amends the original "no glass" decision)

The owner asked for see-through, blurred surfaces after the first no-glass rule was written. It is allowed only in this form:

- **Where glass exists.** Cards are frosted: see-through, lightly blurred (sigma 14) and finely grained, over a page whose colour washes were strengthened (plus two small crisper orbs where cards sit) so the glass is visible (5.13). The bottom navigation bar is see-through with grain, no blur (nothing scrolls under it). Bottom sheets are frosted: the dimmed screen behind is blurred (sigma 22) through them. Everything else stays solid: buttons, input fields, chips, dialogs, snackbars, menus, tonal cards and anything inside the hero.
- **Blur only where there is something to blur.** A card sits on a static, already soft page, so a backdrop filter there would cost a layer per list row and change almost nothing. Blur is used only on sheets, over scrolling content. The bar and the app bar have only the page under them (the screens do not scroll under them), so they are see-through without a blur.
- **Opacity is computed, not picked.** `LpgGlassLook` finds the most transparent fill that keeps primary and secondary text at 4.5:1 on the worst thing behind it: the page's worst pixel for a card, black or white for a sheet (the extremes a blur can average to). The grain speck on top of the glass is counted in the check. Today: cards 0.55 in light and 0.59 in dark, sheets 0.82 in light and 0.96 in dark. The dark sheet is the least see-through because light text needs a darker ground.
- **Shadows go outside.** A drop shadow painted under a see-through fill shows through as a grey patch, so see-through surfaces draw their shadow with the shape cut out (`LpgGlassShadow`).
- **High contrast is never glass.** Opaque, 2 px border, no blur.
- **One file.** Backdrop filters, grain over a surface and see-through fills are made only in `glass.dart`; `surfaces_test` scans the source so they cannot spread.
- **Honest limit.** In the light theme the page's colour is faint (washes at most 16 percent), so a 0.62 white card over it looks almost the same as a solid one; the effect is clearest in dark mode and on sheets.
