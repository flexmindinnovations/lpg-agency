# Status: Mobile UI/UX Revamp, i18n, Device Control and Alert Sounds

**Proposed, not started (plan version 5, 2026-11-05).** Waiting for the owner's answers to the decisions in PLAN.md section 6.

## Done so far
- `lpg-domain-expert` agent created (`.claude/agents/lpg-domain-expert.md`) for wording, flow and domain-visual reviews.
- Existing in-progress UI work saved on branch `wip/mobile-ui-refresh` (unverified).
- Current state surveyed (PLAN.md section 2), including why Linked Devices is empty: no code registers a device, revoking has no effect, and there is no `admin_app` type.
- Owner's inputs recorded: no transparent glass, i18n with JSON catalogues, device control for Driver and Admin, louder custom alert sounds (Driver first).
- Sequencing decided: alert sounds (Epic 12) are built last, after the UI, i18n and device-control work; alerts keep the default sound until then.
- Sound sourcing decided: open source, CC0 first, domain-themed, used only in the three apps' notifications. Candidate sources and licences checked on 2026-11-05 (Freesound CC0 filter, Kenney, akx/Notifications); nothing downloaded yet.
- Notification pipeline surveyed: FCM messages carry no channel, sound or priority; all apps share one default-sound channel.
- The Admin dashboard "error then data" cause is **not yet confirmed**; story 0.4 reproduces and fixes it.

### Fix: provider state survived sign-out (shared-phone data leak) (done, verified by tests)
Found while building R1 (see PR notes): providers lived in one `ProviderScope` for the whole run, so after a sign-out the next person to sign in on the same phone could see the previous person's cached screens (for example the Admin dashboard numbers) until each refreshed.
- **Fix:** `SessionScope` (in `auth`) gives each app a new state tree, via a new key on its `ProviderScope`, whenever a *signed-in* session ends (log out or an expired session). It does not fire when the app starts and finds no session, or on sign-in. All three apps use it in `main.dart`.
- **Tests:** `auth` (key changes only on signed-in to signed-out; discarded state is rebuilt; start-up with no session does not rebuild; repeated sign-outs) and an Admin test with the real dashboard provider: person A's numbers are gone for person B, plus a control test showing A's numbers *do* survive without the scope, which reproduces the bug.
- **Cost:** the screen state is rebuilt on sign-out, which is the point (the app goes to the sign-in screen anyway).
- **Still open (not fixed here):** in the Driver app, a *forced* sign-out (expired session) does not clear the on-device read cache, and neither sign-out path removes the unsent offline queue. A different driver signing in on the same phone could see the previous driver's cached route when offline, and the previous driver's unsent deliveries would be sent under the new session. Clearing the queue on a forced sign-out would lose unsent deliveries, so this needs a decision (keep per-driver queues, or block sign-in until the queue is sent). Added to TASKS.md.

### Fix: offline queue and cache leaked between drivers on a shared phone (done, verified by tests; stacked on the SessionScope fix)
- **Cause:** the offline queue (`sync_operations`) and read cache (`cached_resources`) had no owner. After a forced sign-out the next driver could be shown the previous driver's cached route while offline, and the previous driver's unsent deliveries would have been sent under the next driver's session. (The Customer app shares the same queue.)
- **Chosen design (the plan's open question):** per-user ownership, not wiping. Every queued operation is stamped with the user who queued it and is **sent, counted and listed only under that user's session**; it stays in the queue, **not lost**, and resumes when its owner signs in again. With nobody signed in, nothing is sent. Cache rows carry the owner in their key, so another user never reads them. Wiping on a forced sign-out was rejected because it would silently lose unsent deliveries.
- **Changes:** database schema v5 (`owner_id` on both tables; the cache is rebuilt, the queue is kept); `ResourceCache(owner:)`; `SyncCoordinator(currentOwner:)` is now required, so no caller can forget it; Driver and Customer wire it to the signed-in user; the Driver's cache provider is owner-scoped.
- **Upgrade rule:** operations queued before owners existed have no owner; the first user to sign in after the upgrade adopts them (on a phone with one driver that is their owner; leaving them unowned would strand unsent deliveries). On a phone already shared by two drivers with unsent work, that adoption could assign it to the wrong person; accepted as a one-time edge case.
- **Tests:** `sync_engine` (stamping, never sent under another session and not lost, resumes for its owner, nothing sent when signed out, counts and lists scoped, adoption), `local_storage` (cache scoping, eviction, explicit-logout clear, and a real v4 to v5 migration that keeps queued operations), and a Driver scenario test (driver 2 offline gets nothing of driver 1's).
- **Not covered:** photos and signatures on disk for a queued delivery stay until the delivery is sent (the database is encrypted, those files are not); an explicit log out still clears the whole read cache but leaves the queue, which is intended.
- **Depends on** the `SessionScope` PR: the live counters take their owner when created, and `SessionScope` rebuilds them on sign-out.

## Not done
Everything in TASKS.md.
