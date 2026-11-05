# Plan: Mobile UI/UX Revamp (Customer, Driver, Admin)

> **Status: proposed, awaiting approval.** Requested 2026-11-05. No code is written until the decisions in section 5 are settled.

## 1. Goal

One consistent, stable, modern design across the three mobile apps, built on a single theme engine and one shared component library, with:

- a glass-style look (translucent, blurred surfaces on navigation and sheets) that is **safe on low-end Android**;
- animations and illustrations drawn for LPG work, and a custom domain icon set;
- first-class **tablet** layouts in all three apps;
- loading skeletons before content, and an error screen only when loading has really failed;
- clear validation and error messages in plain English for Indian operations;
- **every user-visible string in one `en.json`**, ready for Hindi and Marathi later.

## 2. Where we are today (checked 2026-11-05)

| Area | State |
|---|---|
| Design system | `mobile/packages/design_system`: 35 components (`Lpg*`), tokens, theme, motion, `LpgAdaptiveShell` (bottom bar on phones, rail on tablets), `LpgMasterDetail`, `LpgSkeleton`. Icons are Lucide with semantic names in `LpgIcons`. |
| Unsaved WIP | Branch `wip/mobile-ui-refresh`: cylinder illustration and card, segmented control, richer dashboard and list screens. Unverified; reused by this plan. |
| Strings | Hardcoded in widgets. Roughly 600 label/title/hint/message properties plus inline text across 3 apps (Admin 89 files, Customer 46, Driver 42). `intl` is used for formatting only; there is no string catalogue. |
| Loading and errors | 129 `.when(...)` call sites. Most use `LpgSkeleton` and `LpgErrorState`, but the pattern is repeated by hand in each screen, so behaviour differs. |
| Tablet | 19 screens/shells are tablet-aware (Admin 9, Customer 6, Driver 4). Admin tablet work landed in #113/#114. Not systematic. |
| Glass | None (`BackdropFilter` is not used). |
| Domain illustrations and icons | None committed; WIP has one cylinder illustration. |

### The Admin dashboard "error first, then data" problem
The Admin dashboard already has a skeleton in its loading branch, so the skeleton is not simply missing. What I know:
- The app turns off Riverpod's automatic retry (`retry: (_, _) => null` in `main.dart`), so a first request that fails stays failed.
- The shell re-fetches the dashboard on a realtime `reconnected` event (`app_shell.dart`). A first request that fails, followed by that refresh succeeding, would produce exactly "error, then data".
- **Not yet confirmed:** why the first request fails (token not ready, network not up, or the 401 refresh path). Story 3.4 starts by reproducing it with request logging. This is the first thing to fix and ships ahead of the rest.

Intended behaviour, for all apps: skeleton until the first response; on failure, retry once quietly (still showing the skeleton); show the error only if that also fails; on refresh, keep the old data on screen.

## 3. Design approach

### 3.1 Theme engine (Epic 1)
- **One source of truth**: design tokens (colour, type, spacing, radius, elevation, motion, blur) feed one `LpgThemeEngine`. Apps pass only an accent and a few flags; they never build their own `ThemeData`.
- Modes: light, dark, high contrast; text scale clamped where layouts are fixed; reduce motion and **reduce transparency** respected.
- Density follows size class (compact phone, medium, expanded tablet).

### 3.2 Glass, done safely (Epic 1, 4)
- One primitive, `LpgGlass` (blur, tint, hairline border, soft highlight), used only where it earns its cost: **navigation bar and rail, app bar, bottom sheets, hero cards**. Content cards stay solid so text stays readable.
- Automatic fallback to a solid surface when the user asks to reduce transparency, in high contrast, on devices that cannot sustain 60 fps with blur (checked by a startup measurement), and in the Driver app by default.
- Text on glass must pass WCAG 2.2 AA (a Phase 1 requirement). Blur never sits behind long text.

### 3.3 Strings (Epic 2)
- One `en.json` per app plus `shared` (design system and core), keyed by feature and screen. Typed access so a missing key fails the build, not the screen. Placeholders and plurals go through the catalogue.
- Tool choice is a spike (story 0.2): a JSON-native typed generator (for example `slang`) against Flutter's own `gen-l10n` (ARB files, which would mean `en.arb` rather than `en.json`). Recommendation to be confirmed: JSON with generated typed keys, because it matches your request and keeps one format for all apps.
- A lint rule in CI fails on new hardcoded user-visible strings.
- Copy is written with the **`lpg-domain-expert`** agent (`.claude/agents/lpg-domain-expert.md`): plain English, domain words used consistently, room for 30 to 40 percent longer Hindi.

### 3.4 Async state system (Epic 3)
- One `LpgAsyncView` (and a sliver version) replaces hand-written `.when(...)` blocks: skeleton, content, empty, error with retry, stale-while-revalidate, offline banner.
- Friendly messages come from an error taxonomy mapped to strings; raw server codes are never shown.
- Skeleton variants match the real layouts (stat tiles, list rows, detail, form), so nothing jumps when content arrives.

### 3.5 Domain icons and illustrations (Epic 5)
- Keep Lucide for generic icons. Add a custom domain set (cylinders by size, van, godown, regulator, delivery code, cash handover, invoice, route, stock count and more), shipped as an icon font so it tints and scales like any icon.
- Vector illustrations for empty, success and error scenes (cylinder, van, godown, receipt). Painted or SVG, small, themed from tokens. A few short animations (success tick, van moving, leak warning), each with a reduce-motion version.
- Subjects and wording reviewed by the domain agent.

### 3.6 Tablet and adaptive (Epic 6)
- Three size classes (compact, medium, expanded) drive layout everywhere: navigation (bar, rail, sidebar), master-detail, multi-column dashboards, forms in dialogs, content max width.
- Priority by real use: **Admin first** (counter and office tablets), then Customer, then Driver (phones in practice; tablet support is kept consistent but least tested).

## 4. Risks

| Risk | Mitigation |
|---|---|
| Blur is expensive on the budget phones drivers use | Glass off by default in Driver; capability check; measured budget in story 0.3; solid fallback always present |
| A trend look hurts sunlight readability and accessibility | High-contrast mode; AA checks in the gallery; glass never behind long text |
| Custom icon and illustration quality needs a designer's eye | Story 5.1 produces a brief; decision 5.4 asks who draws; estimate assumes SVGs we draw ourselves |
| Moving every string is large and breaks tests that find text | Do it per feature with the lint rule, update tests alongside, keep keys stable |
| Three apps share one package, so one change touches all | Gallery app plus golden tests; roll out per app; small reviewed PRs |
| Scope creep ("one more screen") | Stories are per screen group; new asks go to TASKS.md, not into the epic |

## 5. Decisions needed from you

1. **Glass scope.** Navigation, sheets and hero cards only (recommended), or wider? Driver app solid by default (recommended)?
2. **Languages.** English only now, with the catalogue ready for Hindi and Marathi later (recommended)? Or Hindi in this release?
3. **Strings format.** JSON with generated typed keys (recommended) or Flutter's ARB?
4. **Icons and illustrations.** Will we draw them ourselves as SVG (the estimate), or is a designer available?
5. **Low-end device floor.** What is the oldest or cheapest phone the Driver app must run smoothly on (Android version, RAM)?
6. **Tablet priority.** Admin first, Customer second, Driver last (recommended)?
7. **Existing WIP.** Treat `wip/mobile-ui-refresh` as a starting point to rebuild properly, not as finished work (recommended).
8. **Pilot agency.** Is there a real agency, driver and customer we can show builds to before the final release?

## 6. Epics, stories and estimates

Sizes are working days for one developer with AI assistance, including review turn-around of about one day per week. They are estimates, not commitments.

| Epic | Days |
|---|---|
| E0 Discovery and decisions | 3 |
| E1 Theme engine and glass | 5 |
| E2 Strings and copy | 8 |
| E3 Async states (skeletons, errors, retry) | 5 |
| E4 Component library v2 and gallery | 10 |
| E5 Domain icons, illustrations, animation | 8 |
| E6 Tablet and adaptive layout | 6 |
| E7 Customer app rollout | 7 |
| E8 Driver app rollout | 5 |
| E9 Admin app rollout | 12 |
| E10 Quality, accessibility, release | 6 |
| **Total** | **75** |

Stories are listed in [TASKS.md](./TASKS.md).

## 7. Timeline

- **One stream, in order:** about 15 working weeks (75 days) plus review, call it **11 to 15 weeks calendar**.
- **Two or three parallel streams** (theme and async in one, icons and illustrations in another, app rollout after the foundation): **8 to 11 weeks**. Parallel work in the shared design system needs care to avoid conflicts, so I'd run at most two writers there at once.
- **Faster, narrower option (about 5 weeks):** E0 to E3 plus the Admin dashboard and Customer home on the new system, one app fully done as the pattern, the rest later.

Releases:

| Release | Weeks | Contents |
|---|---|---|
| R1 | 1 to 3 | Dashboard flash fixed in all apps, theme engine, strings infrastructure, `LpgAsyncView` |
| R2 | 4 to 7 | Component library v2, icons and illustrations, Customer app on the new system |
| R3 | 8 to 10 | Driver and Admin apps, tablet layouts |
| R4 | 11 to 12 | Quality pass, accessibility, performance, pilot feedback |

## 8. Out of scope

- Backend and API changes (none planned).
- The Angular dashboard's design.
- Translating into Hindi or Marathi (the catalogue is ready for it; translation is a separate piece of work).
- iOS-only polish. The apps run on iOS, but Android is the priority platform.

## 9. Testing and done

Per story: analyze clean, tests pass, golden images for new components, tablet and phone sizes checked, accessibility checked (contrast, touch targets, TalkBack labels). Per epic: gallery updated, `STATUS.md` updated with what was verified and what was not, `planning/current_phase.md` and `knowledge/12-current-status.md` updated. An ADR records the theme engine, strings and glass decisions once approved.
