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

### Story 0.2: i18n tooling spike (done, verified by tests)
Decision and comparison: [i18n-decision.md](./i18n-decision.md). Recommended **slang** (typed JSON, `locale_handling: false`, one `LocalizationsDelegate` per catalogue) over `gen-l10n`; the choice was close and is cheap to reverse. Working example in `design_system` with a second test locale (`hi`) proves: JSON per locale, typed keys (a wrong key is an analyzer error), typed placeholders, plurals, English fallback, runtime switch through `MaterialApp.locale` (also switching Flutter's built-in widget text via `flutter_localizations`), and Indian number and date formats through `intl`. Package versions were read from pub.dev (slang 4.19.2, slang_flutter 4.19.0).
- **Gap found:** a key that exists only in a translation is silently dropped by the generator; story 2.1 adds a CI check.
- **Open product decision (not blocking):** digits for Marathi (native by default in `intl`) versus Latin everywhere for money; recommended Latin. See the decision note.
- **The Hindi strings are test data**, not reviewed translations; they must be replaced before Hindi is offered.
- Pre-existing and unchanged: the next free ADR number is 071 on `main`; none was allocated.

## Not done
Everything in TASKS.md.
