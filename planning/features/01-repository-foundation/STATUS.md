# STATUS — Phase 1: Repository / Development Foundation

**Feature:** 01-repository-foundation
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — 64/67 actionable tasks verified (96%), 1 blocked, all verifications re-run fresh this session**

Every check below was re-executed from scratch this session, not read from a prior report. Nx cache was explicitly bypassed for the frontend re-check. Three things closed that were open at the start of this session: the live **Supabase** connection (T-63), zero test coverage on two shared libraries (DW-21), and PrimeNG installation & integration (T-68).

## Progress

**64 / 67 actionable tasks complete (96%)** · 1 blocked · 2 intentionally not done

| Group | Complete | State |
|---|---|---|
| A — Repository skeleton & Git | 4/4 | ✅ Verified |
| B — Local development environment | 4/4 | ✅ Verified |
| C — Backend foundation (FastAPI) | 14/14 | ✅ Verified |
| D — Frontend foundation (Angular 22 + Nx) | 12/14 | ✅ Verified (1 blocked, 1 deferred, unchanged) |
| E — Flutter foundation | 6/6 | ✅ Verified |
| F — Scripts, CI, documentation | 5/5 | ✅ Verified |
| G — Verification & closeout | 4/4 | ✅ Verified |
| H — Phase 1 close-out | 11/11 | ✅ **Complete — T-63, T-68 closed this session** |
| I — Password rotation (prior session) | included above | ✅ Verified |

---

## This Session's Verification (2026-08-09, re-run)

Every number below came from a command executed in this session.

### Backend — Python 3.13.5 / FastAPI

| Check | Result |
|---|---|
| `ruff check` | ✅ All checks passed |
| `ruff format --check` | ✅ 41 files |
| `mypy --strict` | ✅ 38 source files |
| `lint-imports` | ✅ **5 contracts kept, 0 broken** (50 files, 79 dependencies analyzed) |
| `pytest` | ✅ **83 passed**, 0 skipped — confirms the 21 integration tests genuinely ran against live services, not skipped |
| OpenAPI drift | ✅ Matches, both with and without a real `backend/.env` present (tested both states) |
| Alembic, local `lpg_dev` | ✅ `current`/`heads` clean |
| **Alembic, live Supabase** | ✅ **NEW** — `current`/`heads` clean against the real hosted project |
| Live server, `/health/live` | ✅ 200, correlation ID echoed |
| Live server, `/health/ready` | ✅ **200 `"status":"ready"`**, both dependencies healthy |
| Live server, unknown route | ✅ `application/problem+json`, 404 |

### Frontend — Angular 22.0.8 / Nx 23.1.1

| Check | Result |
|---|---|
| `prettier --check` | ✅ |
| `nx lint` (all, cache bypassed) | ✅ 6 projects — module boundaries intact |
| `nx test` (all, cache bypassed) | ✅ **36 tests** — was 14; **+22 added this session** |
| `nx build` (all, cache bypassed) | ✅ |

**Per-project test breakdown** (first genuine per-project audit — a prior "14 tests" figure had never been broken down by project):

| Project | Tests |
|---|---|
| `dashboard` | 5 |
| `shared-design-tokens` | 5 |
| `shared-data-access` | 4 |
| `shared-ui` | **9 — was 0** |
| `shared-util` | **13 — was 0** |

### Mobile — Flutter 3.44.2

All five packages: format ✅ · analyze ✅ · test ✅ (12 tests, unchanged, not modified this session).

### Repository

| Check | Result |
|---|---|
| Architecture consistency | ✅ 273 files scanned, 0 findings |
| Markdown link integrity | ✅ 133 files, 0 broken links |
| Design token drift | ✅ |
| Workflow YAML | ✅ 4 workflows valid |
| `.env` tracked | ✅ None |
| `service_role` key committed | ✅ None |
| `supabase/migrations/` absent | ✅ |
| Password strings outside `.example`/docs | ✅ Only in `01-init.sql` and `conftest.py`, as expected |
| Supabase CLI present | ✅ 2.113.0 |
| Docker containers | ✅ Both healthy, up ~1 hour |

**Total: 131 tests passing** (83 backend + 36 frontend + 12 Flutter) — up from 102 at last verification.

---

## Closed This Session

### T-63 — Live Supabase connection: BLOCKED → ✅ VERIFIED

The user supplied the Supabase database password. Verified via the application's actual connection path (`Settings.effective_database_url`, the same DSN-composition code the app runs in production) and independently via Alembic:

- `SELECT current_database(), current_user, version()` → PostgreSQL 17.6, `db=postgres`, `user=postgres`
- `alembic current` / `alembic heads` both ran cleanly against the live project
- The credential was never printed in any command output

**Two real findings, not just a pass/fail:**

1. **`postgres` on Supabase has `rolbypassrls=True`.** Not a surprise — `.env.prod.example` already documented this risk — but now confirmed live rather than theoretical. Using this role for the application (not just migrations) would silently void tenant isolation (ADR-017). DW-19 (provision a dedicated `NOSUPERUSER`/`NOBYPASSRLS` role) remains open and is now the concrete next step, not a hypothetical one. **Resolved 2026-08-09** — see "Closed This Session" below.
2. **Only `pgcrypto` is installed** on the live project; `citext` and `pg_trgm` — the other two extensions ADR-013 depends on — are not yet enabled. New: **DW-20**. **Resolved 2026-08-09** — see "Closed This Session" below.

### DW-21 — Zero test coverage on two shared libraries: found and closed

Re-verifying with the Nx cache bypassed (rather than trusting a cached "passed" result) surfaced `"No tests found, exiting with code 0"` for `shared-ui` and `shared-util`. Both had shipped in Phase 1 with implementation but no spec file — the prior "14 tests passing" figure was accurate but had never been broken down per project, so this had gone unnoticed across multiple verification passes.

Closed rather than deferred, since Phase 1's own Definition of Done requires a working testing foundation:

- **`keyboard-shortcuts.service.spec.ts`** (13 tests) — exact modifier matching, metaKey/ctrl equivalence, editable-target exclusion (input/textarea/select/contenteditable), the Escape exception, `preventDefault` only on match, unregister, multi-binding isolation.
- **`data-grid.component.spec.ts`** (9 tests) — **renders real AG Grid Community in jsdom** (not mocked), required `ariaLabel` enforcement, column-definition mapping including a custom `valueFormatter`, default sort/filter/resize behaviour, all three `selectionMode` values, the `ready` output.

The AG Grid test in particular is worth more than its count suggests: it's the first proof that ADR-020's wrapper actually mounts a real grid, not just that its mapping functions compile.

### T-68 — PrimeNG installation & integration: NOT INSTALLED → ✅ COMPLETE

ADR-028's hybrid UI strategy (PrimeNG primary) had been decided but never actually installed. Closed this session:

- Installed `primeng@22.0.0` + `@primeuix/themes@3.0.0` + `primeicons@8.0.0` + `@angular/animations@~22.0.4`, version-matched to installed Angular `~22.0.4` against the npm registry.
- Built `LpgPrimeNgPreset` (`libs/shared/design-tokens/src/lib/primeng-preset.ts`) — every PrimeNG colour, radius, spacing and transition-duration value is `var(--token-name)` or a `color-mix()` derivative of one. No second design system.
- **Found and fixed a pre-existing Phase 1 bug, confirmed with the user before touching already-completed files:** `styles.css` and the AG Grid wrapper referenced `var(--semantic-color-*)` / `var(--semantic-spacing-*)` / `var(--semantic-radius-*)` / `var(--semantic-border-width)` — none of which the token generator has ever emitted (it strips the `semantic` group's prefix to nothing by design; real names are the bare `--color-*` / `--spacing-*` / `--radius-*` / `--border-width`). Introduced in the original Phase 1 commit (`470436e`) — every one of those `var()` references had been silently resolving to nothing since Phase 1 was marked complete. Fixed both files (mechanical rename, no logic change); re-verified light/dark/high-contrast rendering live and AG Grid's own 9-test suite still passes.
- Fixed a real accessibility gap: PrimeNG's `p-dialog` does not return focus to its trigger element on close (no such input exists — checked `primeng-dialog.d.ts`). Added an explicit `viewChild` + `(onHide)` handler; verified Escape closes the dialog and focus returns to the "Open dialog" button (WCAG 2.2 AA, D-35).
- Licence key never hardcoded (same rule as `AG_GRID_LICENSE_KEY`). `prime-license.ts` is git-ignored; `prime-license.example.ts` is the committed template; `app.config.ts` passes the (possibly-`undefined`) key straight into `providePrimeNG({ license: ... })` — its absence never fails the build, PrimeNG just runs unlicensed.
- Verified fresh: `nx build dashboard` (536.39kB initial, under the raised 550kB budget), `nx lint` + `nx test` across `dashboard` / `shared-design-tokens` / `shared-ui`, `prettier --check`, design-token drift check, and live-browser checks (light/dark/high-contrast themes, dialog focus trap and focus-return, breadcrumb/tabs/select/toast/tooltip rendering).

---

## Still Blocked

~~T-34 Playwright e2e execution~~ — **resolved 2026-08-09, Phase 4.** Browser binaries installed; the placeholder smoke test (which asserted content this app never had) rewritten into 4 real tests against the actual shell; 12/12 passed across chromium/firefox/webkit. See `planning/features/04-angular-web-foundation/STATUS.md`.

No blocked items remain from Phase 1.

---

## Intentionally Not Done

| Task | Reason |
|---|---|
| T-35 Storybook | Deferred to Phase 4, where `shared/ui` gains components worth documenting |
| T-52 / T-68 Start Phase 2 | Explicit instruction, every session — Phase 2 remains NOT STARTED |

---

## Known Issues (carried forward, one closed)

1. ~~Live Supabase connectivity unverified~~ — **closed this session.**
2. ~~`citext` and `pg_trgm` not installed on Supabase~~ — **DW-20, resolved 2026-08-09** (Phase 2 close-out). See `planning/features/02-backend-foundation/STATUS.md`.
3. ~~The Supabase application role is not provisioned~~ — **DW-19, resolved 2026-08-09** (Phase 2 close-out). `lpg_app` now provisioned on Supabase, application connects as it, not `postgres`. See `planning/features/02-backend-foundation/STATUS.md`.
4. ~~AG Grid runs on Community, not Enterprise — licence procurement unconfirmed (DW-08)~~ — **resolved 2026-08-09, out of session.** ADR-028 (amends ADR-020) makes AG Grid Community the platform default; DW-08 is no longer a standing blocker, only a per-feature question if a future requirement needs Enterprise. Same session added PrimeNG as the primary component library; **DW-22** (PrimeNG licence-tier eligibility) also resolved 2026-08-09 — product owner confirmed the organisation meets PrimeTek's Community-tier thresholds.
5. **Three documented mobile packages not created** — `api_client`, `auth`, `sync_engine` (DW-17). No content until Phase 6 / Phase 11.

---

## Next

**Phase 2 — Backend Foundation. COMPLETE** (see `planning/features/02-backend-foundation/STATUS.md`), including DW-19 and DW-20, both resolved 2026-08-09. This section is left as it read at Phase 1 close-out for historical accuracy; it is no longer current.

## Last Updated

2026-08-09 (PrimeNG installation & integration, T-68)
