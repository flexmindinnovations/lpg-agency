# 70 — Tasks

- [x] T1 Icon-only row actions with tooltips (shared cell, columns, convention)
- [x] T2 Section cards on dashboard pages
- [x] T3 Section cards in dashboard drawers
- [x] T4 Card convention in `AGENTS.md` and its check
- [x] T5 Backend: held empties endpoint, limit, other sizes, migration, OpenAPI
- [x] T6 Dashboard: show other sizes collected on order detail
- [x] T7 Driver app: collect empties from earlier orders
- [x] T8 Map: address lookup fallbacks; navigate by address when approximate
- [x] T9 Tests, lint, build, browser checks
- [x] T10 Documentation

## Not done (found during this work)

- [ ] CI test APKs are built without `LOCATIONIQ_API_KEY`. Owner's decision: a
  key in a public repository's public APK can be read by anyone.
- [ ] Driver app: held empties are cached only when a stop is opened. Loading
  them for the whole route would cover stops first opened offline.
