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

## Not done
Everything in TASKS.md.
