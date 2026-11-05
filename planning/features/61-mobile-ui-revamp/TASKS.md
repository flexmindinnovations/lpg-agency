# Tasks: Mobile UI/UX Revamp, i18n, Device Control and Alert Sounds

Nothing here is started (plan version 3). Sizes are working days. Order follows the dependencies; E5 and E6 can run beside E3 and E4.

## E0 Discovery and decisions (3 days)
- [ ] 0.1 Design direction: modern solid enterprise look (tonal elevation, radii, type scale, motion language); reference screens for each app (1)
- [ ] 0.2 i18n tooling spike: typed JSON generator versus `gen-l10n`; runtime locale switch, fallback, plurals, a second test locale; pick one with a working example (1)
- [ ] 0.3 Performance baseline on a low-end Android device or emulator; set the frame and startup budget (0.5)
- [ ] 0.4 **Hotfix first:** reproduce the Admin dashboard "error then data", find why the first request fails, fix it, and check Customer and Driver for the same pattern (0.5)

## E1 Theme engine and surfaces (4.5 days)
- [ ] 1.1 Token audit: one source for colour, type, spacing, radius, elevation and motion; remove duplicates and literals (1.5)
- [ ] 1.2 `LpgThemeEngine`: per-app accent, light, dark and high contrast, density by size class, text-scale clamps, reduce motion (2)
- [ ] 1.3 Surface and elevation system (solid tonal layers, soft shadows, hairlines) applied to navigation, app bar, cards and sheets (1)

## E2 i18n, strings and copy (11 days)
- [ ] 2.1 i18n infrastructure: JSON catalogue layout per app and `shared`, typed keys, placeholders and plurals, English fallback for missing keys, CI lint against hardcoded user-visible strings (2.5)
- [ ] 2.2 Runtime language switch (picker, saved per device), `flutter_localizations` for built-in widget text (1)
- [ ] 2.3 Indian formats per locale (₹ lakh grouping, dates, numbers) and bundled font subsets for Indian scripts (1)
- [ ] 2.4 Move and rewrite `design_system` and `core` strings (1)
- [ ] 2.5 Customer app strings, copy reviewed by the domain agent (1.5)
- [ ] 2.6 Driver app strings, reviewed by the domain agent (1)
- [ ] 2.7 Admin app strings, reviewed by the domain agent (2.5)
- [ ] 2.8 Server error codes mapped to catalogue strings (never the server's English text); pseudo-locale test for overflow; tests that look up text updated; every key used and every used key exists (0.5)

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

## E11 Device registration and access control (19.5 days)
Runs as its own stream (release R-D). Applies to the Driver and Admin apps; the Customer app is excluded pending decision 2.
- [ ] 11.1 Design and ADR: data model, states (pending, approved, blocked, removed), enforcement points, grandfathering, privacy; confirm on the agency's real phones what can be read (IMEI, Android ID, model) (1)
- [ ] 11.2 Backend: `admin_app` app type, device table with RLS and migration, repository, register/approve/block/unblock/rename/remove use cases, seat limit from `device_caps`, audit events, domain events (3)
- [ ] 11.3 Backend enforcement: bind sessions to the install ID at sign-in and refresh, check status on every request and on the realtime connection, error codes `DEVICE_PENDING` and `DEVICE_BLOCKED`, short-lived status cache, revoke refresh tokens on block, push and realtime sign-out (3)
- [ ] 11.4 Backend API: register from the app, list, pending, approve, block, unblock, rename, remove, admin alert on a new pending device, grandfathering of existing sessions with a grace period (2)
- [ ] 11.5 Dashboard: Linked Devices page (list, pending, actions, details, IMEI or serial note, filters, history), pending badge in the sidebar, permissions (3)
- [ ] 11.6 Mobile `device_identity` package: install ID in secure storage, device details collection, `X-Device-Id` header in `api_client`, pending and blocked states in session handling (2)
- [ ] 11.7 Driver app: waiting-for-approval and blocked screens, offline queue kept and resumed on unblock, immediate sign-out on block (2)
- [ ] 11.8 Admin app: waiting-for-approval and blocked screens, immediate sign-out on block (1.5)
- [ ] 11.9 (optional, +2) Pairing-code registration mode as a per-agency setting
- [ ] 11.10 Tests and review: tenant isolation, enforcement matrix (unknown, pending, approved, blocked, removed, over the seat limit) on every sign-in and request path, security review (2)
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

## Found while fixing the sign-out leak (needs an owner decision)
- [x] **Driver app: on-device data after a sign-out.** (fixed: owner-scoped queue and cache, see STATUS.md) An expired session does not clear the read cache, and no sign-out removes the unsent offline queue (see STATUS.md). Decide between per-driver queues and cache, or blocking sign-in until the queue is sent, before the pilot (10.4).

## Parking lot (not in scope)
- Hindi, Marathi and other translations; per-language SMS templates with the SMS provider (backend)
- Per-agency choice of sound per event (follows the ADR-068 model)
- Full-screen alerts over the lock screen (restricted by Google Play policy for most apps)
- iOS Critical Alerts (need a special Apple entitlement)
- Angular dashboard redesign
- iOS-specific polish
