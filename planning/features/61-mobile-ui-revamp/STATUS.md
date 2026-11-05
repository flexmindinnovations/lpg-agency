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

### Story 0.1: design direction (done)
[design-direction.md](./design-direction.md): the modern solid enterprise look as rules (tonal elevation, soft shadows, 1 px hairlines, 16 to 20 px radii, type scale, purposeful motion, high contrast, WCAG 2.2 AA), grounded in what the code already has, with one reference screen per app. It is a documentation story: nothing was built or run. Constraint recorded for story 1.1: `tokens.json` is shared with the Angular dashboard. Decision recorded (plan's recommended option): per-app accent proposed as Admin blue, Customer and Driver flame orange; the owner may change it.

## Not done
Everything in TASKS.md.
