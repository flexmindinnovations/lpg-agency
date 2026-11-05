# Plan: Mobile UI/UX Revamp, i18n and Device Control (Customer, Driver, Admin)

> **Status: proposed, awaiting approval (version 2, 2026-11-05).** Updated with the owner's inputs: no transparent glass (a modern, solid, enterprise look instead), i18n with JSON strings from the start, and device registration and access control for the Driver and Admin apps. No code is written until the decisions in section 6 are settled.

## 1. Goal

Three streams that ship separately:

1. **UI revamp.** One consistent, stable, modern look across the three apps, built on a single theme engine and one shared component library, with LPG-specific animation, illustrations and icons, first-class tablet layouts, loading skeletons before content (an error screen only when loading really failed), clear validation messages, and wording that suits Indian operations.
2. **i18n.** Every user-visible string loaded from JSON catalogues (`en.json` now; Hindi, Marathi and other Indian languages later without code changes).
3. **Device control.** An agency decides which phones may use the Driver and Admin apps: devices are registered to the agency, approved, and can be blocked; a blocked or unknown device cannot use the app.

## 2. Where we are today (checked 2026-11-05)

| Area | State |
|---|---|
| Design system | `mobile/packages/design_system`: 35 components (`Lpg*`), tokens, theme, motion, `LpgAdaptiveShell` (bottom bar on phones, rail on tablets), `LpgMasterDetail`, `LpgSkeleton`. Icons are Lucide with semantic names in `LpgIcons`. |
| Unsaved WIP | Branch `wip/mobile-ui-refresh`: cylinder illustration and card, segmented control, richer screens. Unverified; reused by this plan. |
| Strings | Hardcoded in widgets: about 600 label/title/hint/message properties plus inline text across the 3 apps (Admin 89 files, Customer 46, Driver 42). `intl` is used for number and date formatting only; there is no string catalogue. |
| Loading and errors | 129 `.when(...)` call sites using `LpgSkeleton` and `LpgErrorState`, repeated by hand per screen, so behaviour differs. |
| Tablet | 19 screens and shells are tablet-aware (Admin 9, Customer 6, Driver 4); Admin tablet work landed in #113 and #114. Not systematic. |
| Domain illustrations and icons | None committed; the WIP has one cylinder illustration. |

### The Admin dashboard "error first, then data"
The dashboard already has a skeleton in its loading branch, so a missing skeleton is not the whole story. The app turns off Riverpod's automatic retry (`retry: (_, _) => null` in `main.dart`), so a first request that fails stays failed, and the shell refetches the dashboard on a realtime `reconnected` event (`app_shell.dart`). A failed first request followed by that refetch gives exactly "error, then data". **Not yet confirmed:** why the first request fails (token not ready, network not up, or the 401 refresh path). Story 0.4 reproduces it with request logging and fixes it first, ahead of the rest.

Intended behaviour for all apps: skeleton until the first response; on failure retry once quietly (still showing the skeleton); show the error only if that also fails; on refresh keep the old data visible.

### Why Linked Devices is empty today
Checked in the backend and the apps:
- `RegisterDeviceUseCase` (`application/license/manage_devices.py`) **has no caller**. No endpoint registers a device and no mobile code collects any device identity. Linked Devices therefore always lists nothing.
- The only device-related call the apps make is the push registration (`POST /notifications/devices`), which stores a push token against a user. It is a different record and says nothing about who owns the phone.
- **Revoking a device does nothing**: no check anywhere reads a device's status at login or on a request.
- Recognised app types are `customer_app`, `driver_app` and a legacy `warehouse_app`. There is **no `admin_app`**.
- The licence plan can cap devices per app type (`device_caps`); that cap is reusable as the agency's seat limit.
- Refresh tokens exist (`domain/identity/refresh_token.py`), so a session can be tied to a device and cut off when the device is blocked.

## 3. Design approach

### 3.1 Look and feel: modern, solid, enterprise (Epic 1, 4)
No transparency or blur. The reference is the current industry style for business apps (Material 3 and iOS-clean): calm solid surfaces, tonal elevation (a slightly different surface tone per level) with soft shadows and 1 px hairlines, 16 to 20 px corner radii, generous spacing, a clear type scale with bold numbers on stat cards, one strong brand accent with semantic status colours, large touch targets, and purposeful motion (shared-axis page transitions, count-up numbers, press feedback, skeleton shimmer).
Consistency and legibility come first: high-contrast mode, WCAG 2.2 AA contrast (a Phase 1 requirement), and readable in direct sunlight for drivers.

### 3.2 Theme engine (Epic 1)
- One source of truth: design tokens (colour, type, spacing, radius, elevation, motion) feed one `LpgThemeEngine`. Apps pass an accent and a few flags; they never build their own `ThemeData`.
- Modes: light, dark, high contrast. Text scale clamped where layouts are fixed; reduce-motion respected. Density follows size class (compact phone, medium, expanded tablet).

### 3.3 i18n and strings (Epic 2)
- **JSON catalogues per locale**: `en.json` now, `hi.json`, `mr.json` and others later by adding a file, with a fallback to English for any missing key. Strings split by app and `shared` (design system, core).
- **Typed access** so a missing key fails the build, not the screen. Placeholders and plurals go through the catalogue, never string concatenation.
- **Runtime language switch**, saved per device and (later) per user; Flutter's own widget strings (date pickers, dialogs) localised through `flutter_localizations`.
- **Indian formats**: ₹ with lakh grouping, dates like 12 Nov 2026, through `intl` per locale.
- **Fonts for Indian scripts** (for example Noto Sans Devanagari) bundled as subsets so size stays small and glyphs never fall back to boxes.
- **Server messages**: the app translates by error code, never by showing the server's English sentence. Where the server sends text (notifications, SMS), the language preference travels with the user; SMS templates need per-language registration with the provider (separate backend task, listed in the parking lot).
- **Layout safety**: no text baked into images; a "pseudo-locale" (long, accented text) run in tests to catch overflow, because Hindi and Marathi run 30 to 40 percent longer.
- A CI lint fails on new hardcoded user-visible strings.
- Tooling is chosen in a spike (story 0.2): a typed JSON generator such as `slang` against Flutter's `gen-l10n` with ARB files. Recommendation: JSON with generated typed keys, because it matches the requirement and gives one format for all apps.
- Copy is written with the **`lpg-domain-expert`** agent: plain English, domain words used consistently.

### 3.4 Async state system (Epic 3)
One `LpgAsyncView` (and a sliver form) replaces the hand-written `.when(...)` blocks: skeleton, content, empty, error with retry, stale-while-revalidate, offline banner. Friendly messages come from an error taxonomy mapped to strings. Skeleton variants match real layouts so nothing jumps when content arrives.

### 3.5 Domain icons and illustrations (Epic 5)
Lucide stays for generic icons. A custom domain set (cylinders by size, van, godown, regulator, delivery code, cash handover, invoice, route, stock count and more) ships as an icon font so it tints and scales like any icon. Vector illustrations for empty, success and error scenes. A few short animations (success tick, van moving, leak warning), each with a still version for reduce-motion. Subjects reviewed by the domain agent.

### 3.6 Tablet and adaptive (Epic 6)
Three size classes (compact, medium, expanded) drive navigation (bar, rail, sidebar), master-detail, multi-column dashboards, forms in dialogs and content width in every app. Priority: Admin first (counter and office tablets), then Customer, then Driver.

### 3.7 Device registration and access control (Epic 11)

**What identifies a device.** What a normal Android or iOS app can and cannot read decides the design:
- **IMEI and hardware serial cannot be read** by a regular app on Android 10 (API 29) and later; only device-owner (MDM) or carrier-privileged apps can. iOS never exposes them. To be confirmed on the agency's real phones in story 11.1.
- So each app instance creates a random **install ID** kept in secure storage. It is the access key. It survives app restarts and updates and changes on reinstall or data clear.
- The app also reports **manufacturer, model, OS version, app version, platform and the Android ID** (or iOS vendor ID) as supporting identifiers, plus a **device name** the user types at registration (default: the model).
- An admin may type the **IMEI or serial** from the phone's box or settings as an optional asset field, shown in the dashboard. It is a note for the agency's records, not a proof.
- Optional later hardening: Google Play Integrity and Apple App Attest checks to flag rooted, emulated or cloned installs.

**Registration flow (recommended: approve first).**
1. A driver or admin signs in on a new phone. The server sees an install ID it does not know and creates a **pending** device with the details above. The app shows "Waiting for approval" with the device name and a way to check again.
2. The agency admin gets an alert and sees the request under Settings > Linked Devices > **Pending**, with who signed in, phone model and when. They **Approve**, or **Block**.
3. An approved device works. The device counts against the plan's seat limit (`device_caps`) for that app type.
- **Optional stricter mode: pairing code.** The admin registers the device in the dashboard first and gets a one-time code (valid 24 hours, tied to app type); the user enters it at sign-in. Offered as a per-agency setting; story 11.9.

**Enforcement (server-side, not just in the app).**
- Admin and Driver apps send the install ID with every request (`X-Device-Id`) and bind the session to it at sign-in and refresh.
- A request from a device that is unknown, pending, blocked or removed is refused with a clear error code (`DEVICE_PENDING`, `DEVICE_BLOCKED`), and the realtime connection is refused too.
- **Blocking** ends that device's sessions at once (its refresh tokens are revoked) and tells a running app to sign out through realtime and push. Unblocking lets the user sign in again.
- Device status is cached briefly so checks do not add database load, and every register, approve, block, unblock and remove is **audited** (AGENTS security rule), with tenant isolation tests.
- **Offline drivers.** A driver's queued deliveries stay on the phone. If the device is blocked, sync is refused and the queue is kept untouched, with a message to contact the agency. Whether a blocked device's local data is wiped is a decision (section 6).
- **Existing phones** are grandfathered: on their next sign-in after release they register themselves as approved for a grace period set by the agency, so nobody is locked out on release day.

**Dashboard.** Linked Devices becomes a real device list: name, model, OS, app and version, user, status (pending, approved, blocked), registered date, last seen. Actions: approve, block, unblock, rename, add IMEI or serial note, remove. Filters by app and status, a pending badge in the sidebar, a per-user view, and a history of who changed what.

**Customer app: not recommended.** It is used by many households who install freely and sign in with an OTP. Registering and capping their phones would add friction and seats with no safety gain. Controls that fit customers better are blocking a **user account**, session limits and OTP rate limits (already present). The Customer app can still report its device and last-seen time for support, without any approval step. Confirm in section 6.

**Privacy.** Device identifiers are personal data under India's DPDP Act. Collect only what is listed above, say why in the app, set a retention period, and never log identifiers in plain text in application logs. Legal wording is marked unverified, to confirm with the agency's adviser.

## 4. Risks

| Risk | Mitigation |
|---|---|
| IMEI is not available to normal apps | Install ID plus Android ID as the key; IMEI as an admin-typed note (3.7) |
| Locking drivers out on release day | Grandfather existing phones for a grace period; admin override; a clear "ask your agency" screen |
| A driver blocked mid-delivery | Queue kept on the phone; clear message; unblock restores sync; decision on policy in section 6 |
| Reinstall changes the install ID and looks like a new device | Expected; the user shows as a new pending request, the admin removes the old one; Android ID helps spot the same phone |
| Cloned or rooted devices | Optional Play Integrity and App Attest checks as a later story |
| Moving every string is large and breaks tests that find text | Per feature, with the lint rule and stable keys; update tests alongside |
| Three apps share one package, so one change touches all | Gallery app and golden tests; roll out per app; small reviewed PRs |
| Custom icons and illustrations need a designer's eye | Brief in 5.1; decision 6.4 asks who draws; the estimate assumes SVGs we draw ourselves |
| Scope creep | Stories are per screen group; new asks go to TASKS.md, not into an epic |

## 5. Not in this plan
- Backend changes for the UI revamp itself (none), apart from device control (Epic 11).
- Translating into Hindi or Marathi (the catalogue is ready for it; translation and per-language SMS templates are separate work).
- The Angular dashboard's own redesign (only the Linked Devices page changes).
- iOS-only polish. The apps run on iOS, but Android is the priority platform.

## 6. Decisions needed from you

Settled by your last message: no transparent glass; i18n from the start with JSON catalogues; device control for Driver and Admin.

1. **Registration mode.** Approve-first (recommended), pairing code, or both with a per-agency setting?
2. **Customer app.** Confirm it is excluded from device approval (recommended), with only a "last device" record for support.
3. **Who can approve and block devices.** Agency admin only, or managers too?
4. **A blocked driver's local data.** Keep the unsent queue on the phone (recommended) or wipe it?
5. **Existing phones.** Grace period length (suggest 14 days) after which unregistered phones are blocked?
6. **Icons and illustrations.** Do we draw them ourselves as SVG (the estimate), or is a designer available?
7. **Languages.** English only at launch, with the first Indian language added later (recommended). Which language first?
8. **Low-end device floor.** Oldest or cheapest phone the Driver app must run smoothly on (Android version, RAM)?
9. **Tablet priority.** Admin first, Customer second, Driver last (recommended)?
10. **Existing WIP.** Rebuild properly using `wip/mobile-ui-refresh` as a starting point (recommended)?
11. **Pilot agency.** Is there a real agency, driver and customer to show builds to?

## 7. Epics, stories and estimates

Working days for one developer with AI assistance, including about a day of review turn-around per week. Estimates, not commitments.

| Epic | Days |
|---|---|
| E0 Discovery and decisions | 3 |
| E1 Theme engine and surfaces | 4.5 |
| E2 i18n, strings and copy | 11 |
| E3 Async states (skeletons, errors, retry) | 5 |
| E4 Component library v2 and gallery | 10 |
| E5 Domain icons, illustrations, animation | 8 |
| E6 Tablet and adaptive layout | 6 |
| E7 Customer app rollout | 7 |
| E8 Driver app rollout | 5 |
| E9 Admin app rollout | 12 |
| E10 Quality, accessibility, release | 6 |
| E11 Device registration and access control | 19.5 |
| **Total** | **97** |

Optional story 11.9 (pairing code) adds 2 days and Play Integrity or App Attest about 2 more; neither is counted.

Stories are listed in [TASKS.md](./TASKS.md).

## 8. Timeline

Two streams run side by side because device control touches the backend, the dashboard and the apps' sign-in, not the visual design:

- **UI stream (E0 to E10, 77.5 days):** about 8 to 11 weeks with two or three parallel writers; 15 to 18 weeks as one stream in order.
- **Device stream (E11, 19.5 days):** about 4 to 5 weeks on its own, starting right away. Its waiting and blocked screens are first built with today's components and restyled when the new design system lands.
- **Combined, with parallel streams: roughly 10 to 13 weeks.** One developer doing everything in order: about 20 weeks.
- **Narrow option (about 6 weeks):** E0 to E3, the Admin dashboard and Customer home on the new system as the pattern, plus Epic 11, with the rest later.

| Release | Weeks | Contents |
|---|---|---|
| R1 | 1 to 3 | Dashboard flash fixed in all apps, theme engine, i18n infrastructure, `LpgAsyncView` |
| R-D | 1 to 5 | Device registration, approval, blocking and enforcement for Driver and Admin apps, new Linked Devices page |
| R2 | 4 to 7 | Component library v2, icons and illustrations, Customer app on the new system |
| R3 | 8 to 10 | Driver and Admin apps, tablet layouts |
| R4 | 11 to 13 | Quality pass, accessibility, performance, pilot feedback |

## 9. Testing and done

Per story: analyze clean, tests pass, golden images for new components, phone and tablet sizes checked, accessibility checked (contrast, touch targets, TalkBack labels). Device control adds tenant-isolation tests, an enforcement matrix (unknown, pending, approved, blocked, removed, over the seat limit) for every sign-in and request path, and a security review. Per epic: gallery updated, `STATUS.md` records what was verified and what was not, `planning/current_phase.md` and `knowledge/12-current-status.md` updated. An ADR records the theme engine, strings and device-control decisions once approved.
