# Tasks: Mobile UI/UX Revamp, i18n, Device Control and Alert Sounds

Epic 11 (device control) was built first and is merged into this branch; release R1 (epics E0 to E3) is under way in stacked PRs (see [STATUS.md](./STATUS.md)). Ticked stories are implemented and verified; Epic 11 status per story is in the checkboxes below. Sizes are working days. Order follows the dependencies; E5 and E6 can run beside E3 and E4.

## E0 Discovery and decisions (3 days)
- [x] 0.1 Design direction: modern solid enterprise look (tonal elevation, radii, type scale, motion language); reference screens for each app (1)
- [x] 0.2 i18n tooling spike: typed JSON generator versus `gen-l10n`; runtime locale switch, fallback, plurals, a second test locale; pick one with a working example (1)
- [ ] 0.3 Performance baseline on a low-end Android device or emulator; set the frame and startup budget (0.5)
- [x] 0.4 **Hotfix first:** reproduce the Admin dashboard "error then data", find why the first request fails, fix it, and check Customer and Driver for the same pattern (0.5)

## E1 Theme engine and surfaces (4.5 days)
- [x] 1.1 Token audit: one source for colour, type, spacing, radius, elevation and motion; remove duplicates and literals (1.5)
- [x] 1.2 `LpgThemeEngine`: per-app accent, light, dark and high contrast, density by size class, text-scale clamps, reduce motion (2)
- [x] 1.3 Surface and elevation system (solid tonal layers, soft shadows, hairlines) applied to navigation, app bar, cards and sheets (1)

## E2 i18n, strings and copy (11 days)
- [x] 2.1 i18n infrastructure: JSON catalogue layout per app and `shared`, typed keys, placeholders and plurals, English fallback for missing keys, CI lint against hardcoded user-visible strings (2.5)
- [ ] 2.2 Runtime language switch (picker, saved per device), `flutter_localizations` for built-in widget text (1)
- [ ] 2.3 Indian formats per locale (₹ lakh grouping, dates, numbers) and bundled font subsets for Indian scripts (1)
- [ ] 2.4 Move and rewrite `design_system` and `core` strings (1)
- [ ] 2.5 Customer app strings, copy reviewed by the domain agent (1.5)
- [ ] 2.6 Driver app strings, reviewed by the domain agent (1)
- [ ] 2.7 Admin app strings, reviewed by the domain agent (2.5)
- [ ] 2.8 Server error codes mapped to catalogue strings (never the server's English text); pseudo-locale test for overflow; tests that look up text updated; every key used and every used key exists (0.5)

## E3 Async states (5 days)
- [x] 3.1 `LpgAsyncView` and sliver form: skeleton, content, empty, error with retry, keep old data on refresh, offline banner (2)
- [x] 3.2 Error taxonomy mapped to friendly strings and optional small support code (1)
- [x] 3.3 Skeleton variants that match real layouts; shimmer cost checked: one controller per group and a repaint boundary, asserted by tests; frame cost **not measured on a device** (needs 0.3) (1)
- [x] 3.4 Startup and auth gating so first requests wait for a ready session; quiet single retry before showing an error; tests for the sequence (1)

## E4 Component library v2 and gallery (10 days)
- [ ] 4.1 Audit the 35 components: keep, merge, redo (1)
- [~] 4.2 Buttons, fields and validation visuals, selection controls, sheets, dialogs, toasts (3)
  - [x] Audit against the design direction: fields (error border, error icon, red label, 2 px focus border), selection controls, dialogs (20 px+ radius), sheets and toasts (solid inverse surface) already conform; no change
  - [x] Buttons: `LpgButtonSize.large` (64 dp) for the Driver's main delivery actions; a 2 px focus ring set off the button for keyboard users
  - [x] Sheets: visible Close button and an optional subtitle in `LpgFeedback.showSheet` (all 26 sheets get the Close button)
  - [x] Sticky action footer: `LpgSheetLayout` (body scrolls, footer pinned) and `LpgSheetActions` (error banner, full-width primary, optional text secondary); 8 single-action sheets migrated (resolve and assign complaint, add address, record payment, set price, count stock, receive stock, Driver failed delivery)
  - [x] Multi-action sheets on `LpgSheetLayout`: price proposal (Accept / Reject), count review and KYC review (Approve or Verify / Reject, then Reject / Back), compliance document (Renew, then Save renewal / Back), settle trip, and the stock move, return to OMC and receipt sample sheets. `LpgSheetActions` gained a typed second button (`secondaryVariant`, `secondaryIcon`, `isSecondaryLoading`); while either button works, both wait
  - [x] Driver and van detail sheets: the edit forms (van details, driver licence, move branch) pin Save / Cancel and their error; the status action buttons stay in the scrolling body because there can be several
  - [x] `LpgActionRow`: two or more buttons in a row, right aligned with one standard gap (12), the main action last, wrapping right aligned at large text. Used for Admin cash handover (Dispute / Accept & Verify), Driver sync (Discard / Retry) and Admin send-out (Add a driver / Add a van)
  - [ ] Decide whether the equal-width shortcut pairs under a card or hero (customer Call / New order, stock Receive / Count) should also become right-aligned rows
  - [ ] A Driver larger-control pass on fields
- [ ] 4.3 Cards, lists, stat tiles, hero, status, timeline, small charts for the dashboard (3)
  - [x] 4.3a `LpgMetricTile` (figure, label, caption, attention bar) and `LpgHeroStats` (figure strip for hero cards); first used on the Admin dashboard
  - [x] 4.3b `LpgHeroStats` and `LpgMetricTile` rolled out to Customer Home (hero counts) and Driver Today (hero strip, large "Open this stop" button, cash in hand tile); parts of 7.2 and 8.1
  - [x] 4.3c lists, status chips, action cards, section headers: Customer Home recent orders use the shared grouped list with a status chip per row; metric-tile captions use the tone only when the tile needs attention; new `LpgActionCard` (tonal card with the attention bar, icon, title, message, action label) replaces the hand-built live-order card (Customer) and van-load / cash-pending cards (Driver); section headers are bolder and "See all" carries a chevron. The timeline was reviewed against the design direction and left as it is.
  - [ ] 4.3d small charts (a sparkline needs a data source, e.g. a daily trend from the overview API; not built)
- [~] 4.4 Motion kit: page transitions, count-up, press feedback, haptics, all with reduce-motion versions (1)
  - [x] Already in place before this work and checked: count-up, spring press feedback, staggered fade-slide-in, skeleton shimmer, bounded pulse, platform page transitions (instant under reduce-motion)
  - [x] `LpgHaptics` (selection / success / warning) added, used by the quantity stepper, choice chips, bottom tabs and the Driver's delivery-error buzz
  - [ ] Shared-axis page transitions as the direction asks: Flutter's core has none, so this needs the `animations` package (a new dependency, owner's call); until then pages use the platform transitions
- [~] 4.5 Component gallery app, golden tests, accessibility checks (2)
  - [x] `ComponentGallery` page (`package:design_system/gallery.dart`) built from 9 named groups (buttons, fields, status and banners, cards and tiles, hero, lists, timeline, states, navigation)
  - [x] Golden tests: every group in light, dark and high-contrast (27 images, 0.5% tolerance, real Inter and Lucide fonts loaded)
  - [x] Accessibility sweep: every group in every theme at 1x and 2x text: no overflow, tap targets at least 48 dp and labelled, text contrast. It found and fixed three real defects: list-row trailing chip and status-badge label overflowed at 2x text, and the banner action was 32 dp wide
  - [x] Known gap kept visible: light-theme info blue on its tint is 4.37:1, skipped in the sweep for `status_and_banners / light` until story 10.1 decides the shared token
  - [ ] Runnable `example/` app that shows the gallery with theme, accent, text-size and reduce-motion switches (the page exists; the host app does not)

## E5 Domain icons, illustrations, animation (8 days)
- [ ] 5.1 Icon and illustration inventory and brief, with the domain agent (1)
- [ ] 5.2 Custom domain icon set (about 40 icons) as an icon font, mapped in `LpgIcons` (3)
- [ ] 5.3 Illustrations: finish cylinder, add van, godown, receipt and 6 to 8 empty, success and error scenes (3)
- [ ] 5.4 Micro-animations: success tick, van moving, leak warning, each with a still fallback (1)
- [x] 5.5 Illustrated stat cards, pilot: `LpgMetricTile(illustration:)` with four drawn pictures (banknotes, cash received, shortfall, excess), used on the Admin Cash book's four handover tiles. Superseded in part by 5.6
- [x] 5.6 Shared SVG illustrations: the pictures are SVG files in `design_system/assets/illustrations/` (no path data in Dart), recoloured to the tile's tone at render time; 16 pictures; every stat tile in the Admin and Driver apps has one. Open: `LpgActionCard` (Customer dashboard, Driver nudges) and the Customer app's other cards, per-part motion, SVG authoring beyond these 16
- [x] 5.7 Bottom navigation: icons only, the active tab grows into a pill with its label; one continuous motion between tabs (pill widths ease from one tab to the next, label wipes in, icon pops as it fills), instant under reduce-motion. The tablet rail is unchanged
- [x] 5.8 Paper page background: a sheet of paper under every screen with soft blurred colour washes and a fine grain, sized so secondary text keeps 4.5:1 (faint in the light theme, clearly visible in dark). Cards and all other surfaces stay solid. Open: login screens still paint their own plain page
- [x] 5.9 Darker light-theme secondary text (gray-600, 7.6:1 on white; was gray-500, 4.8:1), shared token: mobile and web. Lets the paper page show properly in light
- [x] 5.10 In-app light/dark theme: an Appearance card on each app's profile screen (Match phone / Light / Dark), applied instantly and remembered across restarts. Open: not yet checked on a device in the Customer and Driver apps; Hindi wording unreviewed
- [ ] 5.11 Frosted-glass surfaces (translucent fills with blur and grain on chrome and overlays). Requested; reverses the earlier solid-surfaces-only decision, so it needs a design pass first (see design-direction.md)

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

## E11 Device registration and access control (19.5 days)
Runs as its own stream (release R-D). Applies to the Driver and Admin apps; the Customer app is excluded pending decision 2.
- [ ] 11.1 Design and ADR: data model, states (pending, approved, blocked, removed), enforcement points, grandfathering, privacy; confirm on the agency's real phones what can be read (IMEI, Android ID, model) (1) — **ADR-071 written; the real-phone check is still open** (it needs the agency's phones, which a cloud session cannot do). Grandfathering is replaced by the `device_control` mode (STATUS.md).
- [x] 11.2 Backend: `admin_app` app type, device table with RLS and migration, repository, register/approve/block/unblock/rename/remove use cases, seat limit from `device_caps`, audit events, domain events (3) — done in PR A1 (extends the existing `platform.linked_device` table, which already had RLS; migration `c4e8a1f7d305`). `RegisterDeviceUseCase` has no caller until 11.3.
- [x] 11.3 Backend enforcement: bind sessions to the install ID at sign-in and refresh, check status on every request and on the realtime connection, error codes `DEVICE_PENDING` and `DEVICE_BLOCKED`, short-lived status cache, revoke refresh tokens on block, push and realtime sign-out (3) — done in PR A2 (sessions bound at sign-in/refresh, per-request and realtime checks, refresh tokens revoked on block, `GET /devices/me`, user push on block; mode off/observe/enforce)
- [x] 11.4 Backend API: register from the app, list, pending, approve, block, unblock, rename, remove, admin alert on a new pending device, grandfathering of existing sessions with a grace period (2) — done in PRs A1+A2. "Register from the app" is the sign-in/refresh binding (no separate endpoint); grandfathering is replaced by the per-agency `device_control` mode (`off` by default), so existing phones are unaffected until an admin moves the agency through `observe` to `enforce`.
- [x] 11.5 Dashboard: Linked Devices page (list, pending, actions, details, IMEI or serial note, filters, history), pending badge in the sidebar, permissions (3) — done in PR B: real list with state tabs (Waiting count on its tab) and an app filter; a drawer per phone with approve / block / unblock / remove (block and remove ask first), rename, IMEI/serial note and change history; the `device_control` switch (Off / Watch only / Approve phones) with a confirmation before approving-only; badge on the sidebar Settings item and on Settings > Linked Devices for agency admins; notification click opens the page. Gated by the existing `license:manage_tenant`. Not checked in a browser (see STATUS.md).
- [x] 11.6 Mobile `device_identity` package: install ID in secure storage, device details collection, `X-Device-Id` header in `api_client`, pending and blocked states in session handling (2) — done in PR C: new `mobile/packages/device_identity` (install ID, phone details via `device_info_plus` 13.3.0 / `package_info_plus` 10.2.2 / `android_id` 0.5.2+1, a Dio interceptor that adds the headers and the `device` body object, `GET /devices/me`, the access state machine, router redirect helper). No change to `api_client` or `auth`: the interceptor is added to the `ApiClient`'s Dio at start-up, before the session restore. Also: `RealtimeClient` sends the install ID in its auth frame and has `subscribeToDeviceChanges()`.
- [x] 11.7 Driver app: waiting-for-approval and blocked screens, offline queue kept and resumed on unblock, immediate sign-out on block (2) — done in PR C: "Name this phone", "Waiting for approval" (polls every 15 s and on a button) and "This phone is blocked" screens; `SyncCoordinator` puts an operation refused with `DEVICE_*` back as pending (not failed, not counted as an attempt), stops the pass and resumes when the phone is allowed again; a block signs the user out without touching local data. Verified by tests only, not on a device.
- [x] 11.8 Admin app: waiting-for-approval and blocked screens, immediate sign-out on block (1.5) — done in PR C (same screens, Admin wording, no offline-queue note). Verified by tests only, not on a device.
- [ ] 11.9 (optional, +2) Pairing-code registration mode as a per-agency setting
- [x] 11.10 Tests and review: tenant isolation, enforcement matrix (unknown, pending, approved, blocked, removed, over the seat limit) on every sign-in and request path, security review (2) — done in PR D: `test_device_enforcement_matrix.py` (every state against password and OTP sign-in, refresh, requests, `/devices/me` and a real WebSocket), raw-SQL RLS checks, and `docs/reviews/2026-11-05-device-control-security-review.md` (two findings fixed, residual risks listed; self-review, not independent).
- [ ] 11.11 (optional, about +2) Play Integrity and App Attest checks to flag rooted, emulated or cloned installs

## E12 Alert sounds and delivery reliability (22.5 days), built last
**Starts only when E0 to E9 and E11 have merged** (owner's instruction, 2026-11-05). Release R5. Inside this epic the Driver comes first: items marked A are the Driver slice (about 8 days); the rest follows.
- [ ] 12.0 Entry check: confirm the earlier epics are merged; list every notification event, including the ones device control added, and give each a sound tier; add the sound-settings and setup-guide strings to the catalogue (0.5)
- [ ] 12.1 (A) Audit the push pipeline and write the ADR: event to sound-tier mapping with the domain agent, Android channel plan with versioned IDs, iOS plan (1)
- [ ] 12.2 (A for Driver tiers) Sounds, open source and CC0 first (2):
  - [ ] 12.2a Shortlist three or four candidates per tier from Freesound (CC0 filter), Kenney and akx/Notifications; check each file's own licence page; avoid NC, ND, SA and unclear licences
  - [ ] 12.2b Owner listens and picks one per tier; only then download (filename, source, size stated first)
  - [ ] 12.2c Edit and master with a committed ffmpeg script (trim, fade, two-blast horn pattern, loudness and true-peak ceiling), export Ogg for Android and CAF for iOS, measure against the default sound
  - [ ] 12.2d `LICENSES.md` per sound (URL, author, licence, date checked, saved licence page, our edits), keep the original files, in-app Licences screen only if any CC BY sound is used
- [ ] 12.3 (A) Backend: add a sound tier to each catalogue entry; FCM messages carry the Android channel, sound, high priority and time-to-live, and the iOS sound and interruption level; tests; per-agency sound override left for later (2)
- [ ] 12.4 (A for Driver) Android channels in all three apps: one per tier, versioned IDs, alarm-style audio usage and vibration on Urgent, repeat-until-opened on Urgent, old channel removed on upgrade (3)
- [ ] 12.5 iOS: bundle the sound files, map the payload, time-sensitive interruption level, foreground presentation (1.5)
- [ ] 12.6 Foreground alerts: shared `alerts` package playing the tier sound with haptics and a banner when the app is open (2)
- [ ] 12.7 Driver "New delivery" alert that keeps ringing until acknowledged, on a clear alert screen when the app is open (2)
- [ ] 12.8 (A in lite form) "Make sure you hear alerts" guide: permission, muted-channel detection, per-brand battery and autostart steps for Xiaomi, Oppo, Vivo, Realme and Samsung, a test sound button, volume and Do Not Disturb notes (3)
- [ ] 12.9 Notification settings screen: sound on or off per tier, test sound, link to system channel settings (1.5)
- [ ] 12.10 Delivery tracking: apps report delivered and opened; urgent driver alerts not acknowledged in time can trigger an SMS through the existing SMS channel (2)
- [ ] 12.11 Real-device tests: Samsung, Xiaomi or Redmi, Vivo, Oppo or Realme, a stock Android phone and an iPhone; loudness against the old default, battery saver, Do Not Disturb, background kill; hearing-impaired options (vibration, screen flash) (2)


## Rollout list: hand-written async sites still to convert to `LpgAsyncView` (story 3.1 onward)

Recount on 2026-11-05 after the dashboards were converted: **68 `AsyncValue` sites in 50 files** (an AsyncValue `when`/`maybeWhen` with a `loading:` branch). The plan's "129" counted every `.when(` call, which also matches `Result.when(onSuccess, onFailure)` in providers; those are not async views and need no conversion. Convert per feature during the rollout epics (E7, E8, E9), each with its tests; the first-load rule already holds for all of them through the app-wide quiet retry.

**admin_app** (42 sites in 29 files)
- [ ] `features/approvals/presentation/approvals_screen.dart`
- [ ] `features/cash_book/presentation/cash_book_screen.dart` (2)
- [ ] `features/complaints/presentation/assign_complaint_sheet.dart`
- [ ] `features/complaints/presentation/complaint_detail_screen.dart`
- [ ] `features/complaints/presentation/complaints_screen.dart`
- [ ] `features/compliance/presentation/compliance_screen.dart`
- [ ] `features/customers/presentation/add_customer_screen.dart`
- [ ] `features/customers/presentation/customer_detail_screen.dart` (5)
- [ ] `features/customers/presentation/customers_screen.dart`
- [ ] `features/dispatch/presentation/dispatch_screen.dart` (2)
- [ ] `features/dispatch/presentation/trip_detail_screen.dart`
- [ ] `features/fleet/presentation/driver_form_screen.dart`
- [ ] `features/fleet/presentation/fleet_screen.dart` (2)
- [ ] `features/fleet/presentation/vehicle_form_screen.dart`
- [ ] `features/invoices/presentation/invoice_detail_screen.dart`
- [ ] `features/invoices/presentation/invoices_screen.dart`
- [ ] `features/invoices/presentation/upi_qr_sheet.dart`
- [ ] `features/notifications/presentation/notifications_screen.dart`
- [ ] `features/orders/presentation/create_order_screen.dart`
- [ ] `features/orders/presentation/order_detail_screen.dart`
- [ ] `features/orders/presentation/order_list_screen.dart` (2)
- [ ] `features/orders/presentation/order_settlement.dart`
- [ ] `features/pricing/presentation/pricing_screen.dart`
- [ ] `features/profile/presentation/profile_screen.dart`
- [ ] `features/search/presentation/search_screen.dart`
- [ ] `features/stock/presentation/count_stock_sheet.dart`
- [ ] `features/stock/presentation/receive_stock_sheet.dart`
- [ ] `features/stock/presentation/stock_move_sheets.dart` (2)
- [ ] `features/stock/presentation/stock_screen.dart` (5)

**customer_app** (15 sites in 13 files)
- [ ] `features/dashboard/presentation/notifications_screen.dart`
- [ ] `features/kyc/presentation/kyc_screen.dart`
- [ ] `features/orders/presentation/invoice_detail_screen.dart`
- [ ] `features/orders/presentation/invoice_list_screen.dart`
- [ ] `features/orders/presentation/order_detail_screen.dart`
- [ ] `features/orders/presentation/order_placement_screen.dart` (2)
- [ ] `features/orders/presentation/order_tracking_screen.dart` (2)
- [ ] `features/orders/presentation/orders_screen.dart`
- [ ] `features/orders/presentation/widgets/delivery_code_card.dart`
- [ ] `features/profile/presentation/profile_screen.dart`
- [ ] `features/support/presentation/complaint_detail_screen.dart`
- [ ] `features/support/presentation/raise_complaint_screen.dart`
- [ ] `features/support/presentation/support_screen.dart`

**driver_app** (11 sites in 8 files)
- [ ] `features/cash_handover/presentation/cash_handover_screen.dart`
- [ ] `features/delivery/presentation/deliveries_screen.dart` (2)
- [ ] `features/delivery/presentation/record_delivery_screen.dart` (2)
- [ ] `features/delivery/presentation/stop_detail_screen.dart`
- [ ] `features/delivery/presentation/widgets/stop_map_card.dart`
- [ ] `features/notifications/presentation/notifications_screen.dart`
- [ ] `features/profile/presentation/profile_screen.dart` (2)
- [ ] `features/van_load/presentation/van_load_screen.dart`
## Found while building R1 (not implemented; needs an owner decision or its own story)
- [x] **Provider state survives sign-out.** *Fixed by the session scope (a new state tree whenever a signed-in session ends); see the next section for what remains.* Providers live in one `ProviderScope` for the whole run, so after one person signs out and another signs in on the same phone, cached screens (for example the Admin dashboard) can show the previous person's data until the next refresh. A tenant-data-leak class issue on shared devices. Candidate fix: key the `ProviderScope` on a session counter so every provider is rebuilt on sign-out, with a test per app. Raise with the owner; consider doing it before the pilot (10.4).
- [ ] **Per-app error wording** (domain review of the shared copy): Customer says "contact your gas agency" (not "agency admin"); Admin says "Contact support" where the shared text says "your agency"; Driver needs "Your delivery work is saved and will be sent when you are online" on offline notices, and a refused delivery or cash record must say it was **not** saved (a submit flow, not a load screen); a removed stop should say "Your office may have changed this". Needs per-app copy keys, so do it with the i18n catalogue (2.5 to 2.7).
- [ ] **A "Go back" action** on "not found" and a "Sign in" action on "sign in again" errors (domain review). Needs a navigation callback on `LpgAsyncView`.
- [ ] **Connectivity** is only known in the Driver app. Customer and Admin cannot pass `offline:` to `LpgAsyncView` until a shared connectivity provider exists.
- [ ] The Driver's `CacheFirstReader` rethrows a raw `DioException`; it is classified as "unknown" and shows "We could not load this". Wrap it in `FailureException(mapDioError(e))` so offline and busy show their own wording.
- [ ] **Flaky Driver tests** (pre-existing): `delivery_mutations_test` "departStop..." and `location_sharing_test` "reports a fix..." fail intermittently in full runs.
- [ ] **Light-theme tone contrast** below 4.5:1 (see token-audit.md), decided in 10.1.

## Found while fixing the sign-out leak (needs an owner decision)
- [x] **Driver app: on-device data after a sign-out.** (fixed: owner-scoped queue and cache, see STATUS.md) An expired session does not clear the read cache, and no sign-out removes the unsent offline queue (see STATUS.md). Decide between per-driver queues and cache, or blocking sign-in until the queue is sent, before the pilot (10.4).

## Parking lot (not in scope)
- Hindi, Marathi and other translations; per-language SMS templates with the SMS provider (backend)
- Per-agency choice of sound per event (follows the ADR-068 model)
- Full-screen alerts over the lock screen (restricted by Google Play policy for most apps)
- iOS Critical Alerts (need a special Apple entitlement)
- Angular dashboard redesign
- iOS-specific polish
