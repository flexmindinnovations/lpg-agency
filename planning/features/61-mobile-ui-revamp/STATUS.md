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

### Stories 1.1 to 1.3: token audit, theme engine, surfaces (done, verified by tests)
Details: [token-audit.md](./token-audit.md).
- **1.1 Token audit.** One map of where each token kind lives; no colour literals and no blur existed. Twelve translucent fills made solid (`LpgColors.tint`, `heroMuted/heroSubtle/heroTrack`). A test scans the design system and the three apps and fails on blur or alpha-blended fills outside a short allow-list. Found and fixed muted hero text under AA (3.97:1 to above 4.5:1).
- **1.2 `LpgThemeEngine`.** One engine per app (`accent`, text-scale limit, `reduceMotion`), with light, dark and high-contrast themes from the single token source, `LpgDensity` by size class (`LpgSizeClass`), a text-scale clamp, and reduce motion (platform or forced; page transitions go instant). The three apps use it and build no `ThemeData`.
- **1.3 Surfaces.** Four solid layers (canvas, card, sheet, inverse), `LpgSurface`, hairlines and shadows from one place; dialogs, sheets and menus use the sheet layer, snackbars the inverse layer. `tokens.json` was not touched, so the web build is unaffected.
- **Behaviour changes (deliberate, all small):** Admin now passes the high-contrast theme in dark mode too; dark-mode snackbars are light (inverse layer) instead of card-coloured; text scale is capped at 2.0x; page transitions are instant under reduce motion; solid tints replace translucent ones.
- **Decision recorded:** the per-app accent stays flame orange everywhere (today's colours) so migration changes nothing; the per-app accents proposed in the design note are a one-line change per app once the owner chooses.
- **Found, not fixed (needs a decision, see token-audit.md):** in the light theme, status tone colours as text on their tinted container are under 4.5:1 (accent, success, warning, danger, info, neutral). They come from shared web tokens. A test pins the list so it can only shrink; story 10.1 decides.
- **WIP branch:** `wip/mobile-ui-refresh` was not merged or consulted for code; nothing in this change comes from it.

## Not done
Everything in TASKS.md.
