# Status: Mobile UI Overhaul

**Status:** Built and tested 2026-10-17. **Not yet run on a phone.** Brand assets still pending, so the apps use the default theme.

## Verified (gates re-run, output seen)

| Package | `dart format --set-exit-if-changed` | `flutter analyze` | `flutter test` |
|---|---|---|---|
| `packages/design_system` | clean | 0 issues | 38 passed |
| `apps/customer_app` | clean | 0 issues | 48 passed |
| `apps/driver_app` | clean | 0 issues | 82 passed |

Run with Flutter 3.47.7 (stable). `driver_app/test/offline/delivery_mutations_test.dart` needed a format-only fix to pass the format gate on this version.

No screen in either app uses `Icons.*`, `Colors.*`, hex colours, raw `FontWeight`, or numeric spacing/radius literals (checked with a repo grep).

## Not verified

- Running both apps on a device or emulator; visual review in light, dark and high contrast.
- Screen-reader pass (semantics labels were added but not exercised with TalkBack/VoiceOver).

Design: [PLAN.md](./PLAN.md). Tasks: [TASKS.md](./TASKS.md). Decision: ADR-052.
