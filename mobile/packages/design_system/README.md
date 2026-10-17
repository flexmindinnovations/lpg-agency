# design_system

The shared UI kit for the Customer and Driver apps: generated design tokens,
the Flutter theme built from them, icons, motion, formatting, and the widgets
every screen is assembled from.

```dart
import 'package:design_system/design_system.dart';
```

## Rules for screens

1. **No raw values.** Colours come from `context.lpgColors`, text styles from
   `context.lpgText`, spacing from `LpgSpacing`, radii from `LpgRadius`, sizes
   from `LpgSizes`. No hex colours, no bare `16`s, no `Colors.white`.
2. **No icon fonts.** Use `LpgIcons.<meaning>` (`LpgIcons.orders`,
   `LpgIcons.truck`), never `Icons.*` or a Lucide constant. Add a new semantic
   name to `lib/src/icons.dart` when nothing fits.
3. **Let the theme style Material widgets.** `AppBar(title: Text('Orders'))` is
   already the right colour, size and weight; don't pass `backgroundColor`,
   `elevation` or a title style.
4. **Use the shared states.** Loading lists show `LpgSkeletonList`, failures
   `LpgErrorState`, empty lists `LpgEmptyState`, inline messages `LpgBanner`,
   transient confirmations `LpgFeedback.showToast`.
5. **Format through `LpgFormat`.** Amounts (`LpgFormat.currency`), dates,
   relative times and status labels read the same on every screen.

## What's in it

| Area | API |
|---|---|
| Theme | `LpgTheme.light` / `.dark` / `.highContrast`, `LpgColors` (via `context.lpgColors`) |
| Layout | `LpgSpacing` (`xs` 4 … `xxl` 48, `page` padding), `LpgRadius`, `LpgSizes` |
| Colour roles | `LpgTone` (`primary`, `accent`, `success`, `warning`, `danger`, `info`, `neutral`) |
| Icons | `LpgIcons` (Lucide underneath; `*Filled` = heavier stroke for selected states) |
| Motion | `LpgMotion` durations/springs, `LpgFadeSlideIn` (staggered entrance), `LpgPressable`, `LpgCountUp` |
| Formatting | `LpgFormat.currency`, `.date`, `.dateTime`, `.relative`, `.statusLabel`, `.sentence` |
| Surfaces | `LpgCard` (elevated / outlined / tonal), `LpgHeroCard` (brand gradient) |
| Lists | `LpgListTile`, `LpgSectionHeader`, `LpgKeyValueRow`, `LpgTimeline` |
| Dashboard | `LpgStatTile`, `LpgQuickAction`, `LpgIconBox`, `LpgAvatar`, `LpgBrandMark` |
| Inputs | `LpgButton` (primary / secondary / tonal / text / destructive), `LpgTextField`, `LpgDropdownField`, `LpgChoiceChips`, `LpgQuantityStepper`, `LpgFieldLabel` |
| Testing only | `LpgDevOtpBanner` (sign-in code until the SMS gateway ships) |
| Status | `LpgStatusBadge`, `LpgBanner`, `LpgIconBadgeButton` |
| States | `LpgSkeletonList`, `LpgShimmer` + `LpgSkeleton`, `LpgLoadingIndicator`, `LpgEmptyState`, `LpgErrorState` |
| Feedback | `LpgFeedback.showToast`, `.showSheet`, `.confirm` |
| Navigation | `LpgNavigationBar` + `LpgNavDestination` |

## A typical list screen

```dart
Scaffold(
  appBar: AppBar(title: const Text('Orders')),
  body: ordersAsync.when(
    loading: () => const LpgSkeletonList(),
    error: (e, _) => LpgErrorState(
      message: 'Failed to load orders',
      onRetry: () => ref.invalidate(ordersProvider),
    ),
    data: (orders) => orders.isEmpty
        ? const LpgEmptyState(message: 'No orders yet', icon: LpgIcons.orders)
        : ListView.separated(
            padding: LpgSpacing.page,
            itemCount: orders.length,
            separatorBuilder: (_, _) => const SizedBox(height: LpgSpacing.smd),
            itemBuilder: (context, i) => LpgFadeSlideIn(
              index: i,
              child: LpgCard(onTap: () {}, child: Text(orders[i].reference)),
            ),
          ),
  ),
);
```

## Rebranding

All brand colour lives in two primitive ramps in `design-tokens/tokens.json`:
`gasBlue` (primary) and `flameOrange` (accent). Replace their values with the
brand palette and regenerate:

```sh
node scripts/generate-tokens.mjs
```

That updates the web CSS variables and `lib/src/tokens.dart` together; the
theme, gradients, navigation indicator and every component follow. Keep the
same steps (50 … 900) so light, dark and high-contrast mappings still hold, and
re-check contrast (WCAG 2.2 AA) for text on `actionPrimary`.

The logo: pass the brand image to `LpgBrandMark(image: AssetImage(...))` at the
splash and sign-in call sites, or change `LpgBrandMark`'s default. The
typeface: replace the files in `fonts/inter/` and the `fonts:` block in
`pubspec.yaml`, then update `LpgTheme.fontFamily`.

## Accessibility

- High contrast (`LpgTheme.highContrast`, used automatically when the OS asks
  for it via `MaterialApp.highContrastTheme`) drops shadows and gradients for
  2px borders and solid fills.
- Every animation collapses under the OS reduce-motion setting
  (`MediaQuery.disableAnimations`): entrances render in place, shimmers and
  pulses stop.
- Touch targets are at least 48dp; tappable cards and stat tiles take a single
  `semanticLabel` so screen readers hear one sentence, not every fragment.

## Testing notes

Infinite animations never settle, so `pumpAndSettle` hangs on a screen that is
still loading (spinner or shimmer) — pump the loaded state instead. The
timeline's "current step" pulse is deliberately finite for the same reason.
