# Plan: Mobile UI Overhaul

**Requested:** 2026-10-17 by the product owner ("modern UI for mobile apps using latest UI components, animations, icons and complete UI overhaul for prod").

## Goal

Both Flutter apps (Customer, Driver) look and behave like one production product, built from a single design system, so that:

- every screen uses the same tokens, components, icons, motion and formatting;
- the brand (logo, colours, typeface) can be swapped later in one place, because brand assets have not been supplied yet;
- new screens from the parallel workstreams (Razorpay checkout, SMS, WhatsApp ordering) can adopt it without writing styling of their own.

## Scope

**In:** `mobile/packages/design_system`, every screen in `mobile/apps/customer_app` and `mobile/apps/driver_app`, their widget tests where copy or widgets changed, ADR-052.

**Out:** behaviour changes (API calls, providers, routing, offline queue), new features, real brand assets, golden/screenshot tests.

## Design

### Design system (`packages/design_system`, 0.2.0)

| Area | What |
|---|---|
| Tokens | Still generated from `design-tokens/tokens.json` by `scripts/generate-tokens.mjs`; nothing hand-edited |
| Theme | `LpgColors` ThemeExtension (text, surfaces, canvas/card roles, status, hero gradient, elevation shadows), full Material 3 component themes, light / dark / high contrast |
| Layout | `LpgSpacing`, `LpgRadius`, `LpgSizes` (48dp touch targets) |
| Typography | Inter bundled in the package (OFL), weights 400–800 |
| Icons | `LpgIcons` semantic names over Lucide (`lucide_icons_flutter`) |
| Motion | `LpgMotion` durations/springs, `LpgFadeSlideIn`, `LpgPressable`, `LpgCountUp`; all collapse under reduce-motion and none loop forever in a loaded state |
| Formatting | `LpgFormat` (en_IN rupees, dates, relative time, status labels) |
| Components | Buttons, cards, hero card, list tile, section header, key-value row, timeline, stat tile, quick action, avatar, brand mark, banner, status badge, text field, dropdown, choice chips, quantity stepper, skeletons, empty/error states, feedback (toast, sheet, confirm), navigation bar, icon badge button, dev OTP banner |

### Apps

- Each app keeps status → label/severity/icon mapping in one presentation file (`order_presentation.dart`, `invoice_presentation.dart`, `complaint_presentation.dart`) so a status never reads differently on two screens.
- Loading → skeletons, failure → `LpgErrorState` with Retry, empty → `LpgEmptyState`, confirmations → `LpgFeedback`.
- The Customer App's add/edit address screens share one `AddressFormFields`; the app-local `form_field_widgets.dart` is removed.
- `MaterialApp.highContrastTheme` is set in both apps.

## Testing

`dart format --set-exit-if-changed`, `flutter analyze` and `flutter test` for `design_system`, `customer_app` and `driver_app` (the CI matrix). Existing widget tests updated only where copy or widget types changed on purpose.

## Risks

- Other threads add screens on the same branch base; they should build on `design_system` rather than raw Material styling (README "Rules for screens").
- ADR and feature numbers may collide with parallel threads; renumber at merge if so.
