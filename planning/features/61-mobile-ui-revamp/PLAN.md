# Plan: Mobile UI/UX Revamp, i18n, Device Control and Alert Sounds (Customer, Driver, Admin)

> **Status: proposed, awaiting approval (version 5, 2026-11-05).** Updated with the owner's inputs: no transparent glass (a modern, solid, enterprise look instead), i18n with JSON strings from the start, device registration and access control for the Driver and Admin apps, and custom, louder alert sounds built from open-source (CC0-first) domain-themed recordings, used only as notification sounds in the three apps (most urgent for the Driver app), **built last, after the other changes are done**. No code is written until the decisions in section 6 are settled.

## 1. Goal

Four streams that ship separately:

1. **UI revamp.** One consistent, stable, modern look across the three apps, built on a single theme engine and one shared component library, with LPG-specific animation, illustrations and icons, first-class tablet layouts, loading skeletons before content (an error screen only when loading really failed), clear validation messages, and wording that suits Indian operations.
2. **i18n.** Every user-visible string loaded from JSON catalogues (`en.json` now; Hindi, Marathi and other Indian languages later without code changes).
3. **Device control.** An agency decides which phones may use the Driver and Admin apps: devices are registered to the agency, approved, and can be blocked; a blocked or unknown device cannot use the app.
4. **Alert sounds.** Custom, clearly louder notification sounds in the style of food-delivery apps, with the Driver app first: a new delivery must be heard on a busy road, and a missed alert must be rare. **Sequenced last (owner's instruction, 2026-11-05):** the other streams ship first and the sound integration follows once they are done. Until then, alerts keep today's default sound.

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

### Notifications today
Checked in the backend and the apps:
- The backend sends a plain FCM `notification` (title and body) plus a `data` block, with **no Android channel, sound, priority or time-to-live settings** (`infrastructure/channels/push_channel.py`). iOS only gets `content-available`.
- All three apps create **one shared Android channel**, `lpg_default_channel`, at high importance and the **default system sound**. Every event type therefore sounds the same, and it is the quietest sound on the phone.
- The notification catalogue (`infrastructure/notification/catalog.py`) already lists every event and its audience (customer, driver, staff), so each event can be given a sound tier. Agencies can already switch channels per event (ADR-068); the catalogue marks critical events.
- Android fixes a channel's sound when the channel is first created, and the user can mute or lower it in system settings. A different sound therefore needs **new channel IDs**, and the app cannot override a muted channel.

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

### 3.8 Alert sounds (Epic 12), built last

**Sequencing.** Epic 12 starts when the UI, i18n and device-control work (E0 to E9, E11) has merged. Reasons: the sound settings screen, the "Make sure you hear alerts" guide and the "New delivery" alert screen are built once with the new components and strings instead of twice; the Android and iOS notification code in each app's push service is touched by the revamp and by device control (blocked-device sign-out), so doing it afterwards avoids conflicts; and the new notification events that device control adds get their sound tier in one pass.

**What earlier epics must do so this is easy later (small, no sound work):**
- Any new notification event added before Epic 12 (for example "device waiting for approval" and "device blocked" in Epic 11) goes into the catalogue as normal; Epic 12 story 12.0 gives every event without a tier one.
- Push handling in the apps stays in `push_notification_service.dart` and is not duplicated, so Epic 12 changes one file per app.
- Strings for the sound settings and setup guide are added to the catalogue when Epic 12 starts, not before.
- Nothing before Epic 12 changes the push payload shape, so the backend change in 12.3 is a pure addition.


**What "louder" can and cannot mean.** An app cannot raise the phone's volume setting. What an app can do, and what delivery apps do:
- ship a **loud, short, distinctive sound** mastered to a high, consistent loudness (not the quiet default tone), so it cuts through traffic at the same volume setting;
- play urgent alerts on the **alarm or ringtone audio stream** (Android audio attributes), which users usually keep higher than the notification volume;
- **repeat** the sound until the notification is opened or dismissed (Android's insistent flag), the way a new-order ring works;
- add a strong **vibration pattern** and a heads-up banner;
- play the sound inside the app when it is open (the system shows nothing then);
- make sure the alert **arrives at all**: high priority, a short time-to-live so old alerts do not ring late, and help with the battery and autostart settings that stop alerts on many Indian phones (Xiaomi, Oppo, Vivo, Realme, Samsung).

**Sound tiers.** Four sounds with one family feel, each with a domain theme, mapped from the catalogue:

| Tier | Sound and domain theme | Used for |
|---|---|---|
| Urgent | Loud, 6 to 8 seconds, repeats until opened (Driver and Admin). Theme: two short truck-horn blasts | Driver: new route or delivery assigned, route cancelled, stop cancelled. Admin: cancellation waiting for approval, failed delivery, order that cannot be assigned, cash shortfall, expiring compliance document |
| Standard | Clear chime, about 2 seconds. Theme: double bicycle-bell ring | Driver: route re-ordered, reminder. Admin: new order, new complaint, stale unassigned order |
| Soft | Gentle tone, about 1 second. Theme: cash-register ding | Order delivered (staff), payment received, invoices |
| Friendly | Warm, short. Theme: soft single bell | Customer: confirmed, out for delivery, delivered |

The mapping is a field on each catalogue entry, so it can be changed without app releases. Per-agency choice of sound per event can follow ADR-068's model later.

**Android.** One notification channel per tier, with **versioned IDs** (for example `lpg_urgent_v1`) so a sound can be changed in a later release; old channels are removed on upgrade. Urgent channels use maximum importance, an alarm-style audio usage, vibration and lights. The backend names the channel and sound in each message. Sounds ship as raw resources.

**iOS.** The same sounds as `.caf` files (under 30 seconds) in the app bundle, named in the push payload, with the "time-sensitive" interruption level so alerts break through Focus modes. iOS cannot go louder than the ring volume, and *Critical Alerts* need a special Apple approval, so they are not planned.

**In the app.**
- A shared alerts package plays sounds in the foreground with haptics and a banner.
- The Driver's new-delivery alert **keeps ringing until the driver acknowledges it**, on a clear "New delivery" alert screen when the app is open. Showing a full-screen alert over the lock screen is restricted by Google Play policy for most apps, so it is not planned; a repeating heads-up notification is used instead.
- A **"Make sure you hear alerts"** guide: notification permission (Android 13 and later), a check that detects a muted or low-importance channel and warns, step-by-step help for each common phone brand's battery and autostart settings, a **test sound** button, a volume reminder and a note about Do Not Disturb.
- A notification settings screen: sound on or off per tier, test sound, a link to the system channel settings.
- **Delivery tracking**: the app tells the server when an alert was delivered and opened; if an urgent driver alert is not acknowledged within a set time, the server can send an SMS through the existing SMS channel (a cost to confirm).

**Sounds themselves: open source, CC0 first, notification use only.**

*Licence rules.*
- **First choice: CC0** (public domain dedication): no attribution, no restriction on modifying or bundling.
- **Second choice: CC BY** only if no CC0 sound fits. It needs a credits line in an in-app "Licences" screen.
- **Not used:** CC BY-NC (non-commercial), CC BY-ND (no changes, but we must trim and master), CC BY-SA (share-alike), Freesound's older "Sampling+", site licences that forbid redistribution or are "personal use" only, AI-generated clips of unclear licence, and any sound taken from another company's app, film or advert.
- **Our own use rule:** the files go only into the three apps' notification assets (Android raw resources, iOS bundle, and the shared alerts package). They are not used in the dashboard, marketing or anywhere else, and are not republished as a sound pack. CC0 would allow more; this is our policy, as requested.
- **Paper trail.** A `LICENSES.md` beside the sounds lists every file: source URL, author, licence, the date we checked the licence page, a saved copy of that page, and what we changed. We keep our own copy of each original, because a site can remove a sound later. Uploaders' CC0 declarations are not independently verified by the site, so we choose original field recordings and avoid anything that sounds ripped from a film or a known brand.

*Where candidates come from (checked 2026-11-05, nothing downloaded):*

| Source | Licence as shown | Notes |
|---|---|---|
| [Freesound](https://freesound.org) with the "Creative Commons 0" filter | CC0 per sound (re-check each sound's own page) | Largest pool. Truck-horn search returns about 100 CC0 results, including short honks such as "truck real horn honk quick polite warning" (about 3 s) and "Truck_horns" (about 5 s). Bicycle-bell and cash-register searches also return many CC0 results, for example "bell toy cash register ding". Gas-hiss and metal-clang searches are still to do. |
| [Kenney](https://kenney.nl/assets/category:Audio) packs (Interface Sounds, Digital Audio, UI Audio) | Interface Sounds page states "Creative Commons CC0"; the other packs' pages to be checked | Clean, short UI tones; good for the Standard and Soft tiers. Not domain-themed. |
| [akx/Notifications](https://github.com/akx/Notifications) | Dual: CC0 or CC BY 3.0, our choice is CC0 | Subtle hand-made tones; would need heavy mastering, so likely only for the Friendly tier. |

*Sound quality work (story 12.2).* Open-source recordings are rarely loud or consistent, so each chosen file is trimmed, faded, shaped and **loudness-mastered** with a committed, repeatable script (ffmpeg): a high, consistent loudness with a true-peak ceiling so it does not clip, exported to Ogg for Android and CAF for iOS (iOS limit: 30 seconds). Targets are proposed and checked on real phones against the default sound, measured the same way. Urgent is built from a truck-horn recording, which is naturally loud and cuts through road noise, edited into a recognisable two-blast pattern so it does not sound like a generic horn.

*Process.* We shortlist three or four candidates per tier, you listen and pick one per tier, and only then do we download them (filename, source and size stated first).

**Safety and courtesy.** Loud means clear, not painful: consistent loudness with headroom, no clipping, and a quiet-hours setting for Admin. Hearing-impaired users get vibration and a screen flash option.

## 4. Risks

| Risk | Mitigation |
|---|---|
| IMEI is not available to normal apps | Install ID plus Android ID as the key; IMEI as an admin-typed note (3.7) |
| Locking drivers out on release day | Grandfather existing phones for a grace period; admin override; a clear "ask your agency" screen |
| A driver blocked mid-delivery | Queue kept on the phone; clear message; unblock restores sync; decision on policy in section 6 |
| Reinstall changes the install ID and looks like a new device | Expected; the user shows as a new pending request, the admin removes the old one; Android ID helps spot the same phone |
| Cloned or rooted devices | Optional Play Integrity and App Attest checks as a later story |
| The sound is loud but the alert still does not arrive (battery savers kill the app on many Indian phones) | In-app setup guide per phone brand, high-priority delivery, delivery tracking and an SMS fallback for urgent driver alerts; tested on a real-device matrix |
| The driver muted or lowered the channel in system settings | The app detects it and warns; test sound button; channel settings link |
| Changing a sound later does not take effect (Android freezes channel sounds) | Versioned channel IDs from the start |
| Sound licensing | CC0 first, CC BY only with a credits screen, no NC/ND/SA; per-file `LICENSES.md` with a saved copy of the licence page and of the original file; notification-only use |
| Open-source sounds sound generic or are also used in other apps | Edit and layer (for example a two-blast horn pattern) so the set is recognisable as ours; listen-and-pick by you before anything ships |
| An uploader's CC0 claim turns out to be wrong | Prefer original field recordings; avoid anything that resembles a film, TV or brand sound; keep the evidence; replacing a file is a one-file change |
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
12. **Sound shortlist.** Decided: open-source, CC0-first sounds, used only in the three apps' notifications. What I need: you listen to the shortlist from story 12.2 and pick one per tier. No file is downloaded before that.
13. **Which events are Urgent.** Is the table in section 3.8 right for Driver and Admin?
14. **Repeat until opened.** Acceptable for the Driver's new-delivery alert (and for Admin's urgent alerts), given the battery and annoyance cost?
15. **Quiet hours.** For Admin only, or also an option for drivers outside their shift?
16. **SMS fallback.** If an urgent driver alert is not acknowledged in a few minutes, send an SMS (extra cost per message)?
17. **Customer app sounds.** A short friendly custom sound, or leave the system default?
18. **Test phones.** Which real phones do the drivers and admins use? We need one each of the common brands to test sound and background delivery.

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
| E12 Alert sounds and delivery reliability (built last) | 22.5 |
| **Total** | **119.5** |

Optional story 11.9 (pairing code) adds 2 days and Play Integrity or App Attest about 2 more; commissioning custom sounds from a designer adds elapsed time but little effort; none of these is counted.

Stories are listed in [TASKS.md](./TASKS.md).

## 8. Timeline

Two streams run side by side first, because device control touches the backend, the dashboard and the apps' sign-in rather than the visual design. **Alert sounds (Epic 12) follow once those are done.**

- **UI stream (E0 to E10, 77.5 days):** about 8 to 11 weeks with two or three parallel writers; 15 to 18 weeks as one stream in order.
- **Device stream (E11, 19.5 days):** about 4 to 5 weeks on its own, starting right away. Its waiting and blocked screens are first built with today's components and restyled when the new design system lands.
- **Alert stream (E12, 22.5 days), last:** about 5 weeks. It starts when E0 to E9 and E11 have merged and can overlap the quality pass (E10), since it changes notification code rather than screens. Until then, alerts keep today's default sound.
- **Combined: roughly 14 to 16 weeks.** One developer doing everything in order: about 24 weeks.
- **Narrow option (about 6 weeks, first part):** E0 to E3, the Admin dashboard and Customer home on the new system as the pattern, plus Epic 11. The rest, and then the alert sounds, follow.

| Release | Weeks | Contents |
|---|---|---|
| R1 | 1 to 3 | Dashboard flash fixed in all apps, theme engine, i18n infrastructure, `LpgAsyncView` |
| R-D | 1 to 5 | Device registration, approval, blocking and enforcement for Driver and Admin apps, new Linked Devices page |
| R2 | 4 to 7 | Component library v2, icons and illustrations, Customer app on the new system |
| R3 | 8 to 10 | Driver and Admin apps, tablet layouts |
| R4 | 11 to 13 | Quality pass, accessibility, performance, pilot feedback |
| R5 | 11 to 16 | **Alert sounds**: Driver first (louder new-delivery alert, per-tier channels, backend payload, setup guide), then Admin and Customer, iOS, foreground alerts, repeat-until-acknowledged, brand-specific battery guides, delivery tracking and SMS fallback |

## 9. Testing and done

Per story: analyze clean, tests pass, golden images for new components, phone and tablet sizes checked, accessibility checked (contrast, touch targets, TalkBack labels). Device control adds tenant-isolation tests, an enforcement matrix (unknown, pending, approved, blocked, removed, over the seat limit) for every sign-in and request path, and a security review. Per epic: gallery updated, `STATUS.md` records what was verified and what was not, `planning/current_phase.md` and `knowledge/12-current-status.md` updated. Alert sounds add a loudness check against the old default on real phones, a delivery test in battery-saver and Do Not Disturb, and a check on each test brand. An ADR records the theme engine, strings, device-control and alert-sound decisions once approved.
