# Tasks: Mobile UI/UX Revamp

Nothing here is started. Sizes are working days. Order follows the dependencies; E5 and E6 can run beside E3 and E4.

## E0 Discovery and decisions (3 days)
- [ ] 0.1 Design direction and glass spec: surfaces, blur, tint, fallbacks, where glass is and is not used (1)
- [ ] 0.2 Strings tooling spike: typed JSON generator versus `gen-l10n`; pick one with a working example in the gallery (1)
- [ ] 0.3 Performance baseline on a low-end Android device or emulator; set the frame and startup budget (0.5)
- [ ] 0.4 **Hotfix first:** reproduce the Admin dashboard "error then data", find why the first request fails, fix it, and check Customer and Driver for the same pattern (0.5)

## E1 Theme engine and glass (5 days)
- [ ] 1.1 Token audit: one source for colour, type, spacing, radius, elevation, motion and blur; remove duplicates and literals (1.5)
- [ ] 1.2 `LpgThemeEngine`: per-app accent, light, dark and high contrast, density by size class, text-scale clamps, reduce motion and reduce transparency (2)
- [ ] 1.3 `LpgGlass` primitive with capability fallback; apply to navigation bar, rail, app bar and sheets (1.5)

## E2 Strings and copy (8 days)
- [ ] 2.1 String catalogue infrastructure: file layout, typed keys, placeholders and plurals, CI lint against hardcoded user-visible strings (2)
- [ ] 2.2 Move and rewrite `design_system` and `core` strings (1)
- [ ] 2.3 Customer app strings, copy reviewed by the domain agent (1.5)
- [ ] 2.4 Driver app strings, reviewed by the domain agent (1)
- [ ] 2.5 Admin app strings, reviewed by the domain agent (2.5)
- [ ] 2.6 Update tests that look up text; add a test that every key is used and every used key exists (in 2.2 to 2.5)

## E3 Async states (5 days)
- [ ] 3.1 `LpgAsyncView` and sliver form: skeleton, content, empty, error with retry, keep old data on refresh, offline banner (2)
- [ ] 3.2 Error taxonomy mapped to friendly strings and optional small support code (1)
- [ ] 3.3 Skeleton variants that match real layouts; shimmer cost checked (1)
- [ ] 3.4 Startup and auth gating so first requests wait for a ready session; quiet single retry before showing an error; tests for the sequence (1)

## E4 Component library v2 and gallery (10 days)
- [ ] 4.1 Audit the 35 components: keep, merge, redo (1)
- [ ] 4.2 Buttons, fields and validation visuals, selection controls, sheets, dialogs, toasts (3)
- [ ] 4.3 Cards, lists, stat tiles, hero, status, timeline, small charts for the dashboard (3)
- [ ] 4.4 Motion kit: page transitions, count-up, press feedback, haptics, all with reduce-motion versions (1)
- [ ] 4.5 Component gallery app, golden tests, accessibility checks (2)

## E5 Domain icons, illustrations, animation (8 days)
- [ ] 5.1 Icon and illustration inventory and brief, with the domain agent (1)
- [ ] 5.2 Custom domain icon set (about 40 icons) as an icon font, mapped in `LpgIcons` (3)
- [ ] 5.3 Illustrations: finish cylinder, add van, godown, receipt and 6 to 8 empty, success and error scenes (3)
- [ ] 5.4 Micro-animations: success tick, van moving, leak warning, each with a still fallback (1)

## E6 Tablet and adaptive layout (6 days)
- [ ] 6.1 Size classes and a responsive layout system: content width, grid, spacing (1)
- [ ] 6.2 Navigation per size class: bar, rail, sidebar, in each app (1)
- [ ] 6.3 Master-detail, multi-column dashboards, forms in dialogs (2)
- [ ] 6.4 Landscape, keyboard and mouse hover, split-screen, large text; golden tests at three sizes (2)

## E7 Customer app rollout (7 days)
- [ ] 7.1 Shell, sign-in and onboarding screens (1.5)
- [ ] 7.2 Home and orders list, order detail (2)
- [ ] 7.3 Order placement, payment, UPI and online (2)
- [ ] 7.4 Support, profile, notifications (1.5)

## E8 Driver app rollout (5 days)
- [ ] 8.1 Shell, sign-in, Today and deliveries (1.5)
- [ ] 8.2 Stop detail, record delivery, delivery code, UPI QR (2)
- [ ] 8.3 Van load, cash handover, sync status, profile (1.5)

## E9 Admin app rollout (12 days)
- [ ] 9.1 Shell, sign-in, Dashboard (2)
- [ ] 9.2 Orders and dispatch (2.5)
- [ ] 9.3 Customers and complaints (2)
- [ ] 9.4 Invoices, payments, cash book (2)
- [ ] 9.5 Stock, pricing, fleet, drivers, compliance (2.5)
- [ ] 9.6 More, settings, notifications (1)

## E10 Quality and release (6 days)
- [ ] 10.1 Accessibility audit: contrast, touch targets, TalkBack, large text (1.5)
- [ ] 10.2 Performance pass on the low-end device against the E0 budget (1.5)
- [ ] 10.3 Domain review of every screen's wording and flow by the domain agent; fixes (1)
- [ ] 10.4 Pilot builds with a real agency, driver and customer; fixes (1)
- [ ] 10.5 Release notes, `STATUS.md`, `current_phase.md`, ADR, knowledge summary (1)

## Parking lot (not in scope)
- Hindi and Marathi translations
- Angular dashboard redesign
- iOS-specific polish
