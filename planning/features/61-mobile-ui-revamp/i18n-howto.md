# i18n how-to (story 2.1)

Decision and reasons: [i18n-decision.md](./i18n-decision.md). Tool: **slang** (typed JSON catalogues, generated Dart), delivered through one Flutter `LocalizationsDelegate` per catalogue so `MaterialApp.locale` is the single source of truth for the language.

## Where things live
| What | Where | Class |
|---|---|---|
| Shared strings (design-system components, errors) | `mobile/packages/design_system/lib/src/i18n/*.i18n.json` | `LpgStrings`, `context.lpgStrings` |
| Admin app strings | `mobile/apps/admin_app/lib/src/i18n/*.i18n.json` | `AdminStrings`, `context.strings` |
| Customer app strings | `mobile/apps/customer_app/lib/src/i18n/*.i18n.json` | `CustomerStrings`, `context.strings` |
| Driver app strings | `mobile/apps/driver_app/lib/src/i18n/*.i18n.json` | `DriverStrings`, `context.strings` |

Each catalogue has `slang.yaml` (next to the package's `pubspec.yaml`), `en.i18n.json` (the base language) and one `<code>.i18n.json` per extra language. Generated `strings*.g.dart` files are **committed** (a narrow exception to the `*.g.dart` ignore rule in `.gitignore`) and must not be edited.

## Add or change a string
1. Edit `en.i18n.json`; nest by feature and screen (`"orders": {"detail": {"title": "Order {number: String}"}}`).
2. `dart run slang` in that package or app, commit the generated files.
3. Use it: `Text(context.strings.orders.detail.title(number: order.number))`. A wrong key or a missing placeholder is an analyzer error, so it fails the build, not the screen.
- Placeholders are typed in the string: `{count: int}`, `{time: String}`. Never join pieces of a sentence in code.
- Plurals use the plural keys `one` and `other` with `{n}`: `"cylinders": {"one": "{n} cylinder", "other": "{n} cylinders"}`, called as `cylinders(n: 3)`.
- Wording: plain English a Class 8 reader follows, say what happened then what to do, no raw server text. Have the `lpg-domain-expert` agent review new copy.

## Add a language (Hindi, Marathi, ...)
1. Add `hi.i18n.json` beside `en.i18n.json` in each catalogue (a missing key shows English).
2. `dart run slang`, commit.
3. List the language in the app's `<app>LaunchLocales` (for example `[Locale('en'), Locale('hi')]`). **English only at launch**: until then a device set to another language still gets English.
4. Replace the test data: the `hi.i18n.json` in `design_system` is a handful of strings written to prove the machinery. It was not reviewed by a Hindi speaker.

## Switch language at runtime
`ref.read(lpgLocaleProvider.notifier).select(const Locale('hi'))`; `select(null)` follows the device again. Each app's root `MaterialApp.router` watches `lpgLocaleProvider`. The picker and saving the choice per device are story 2.2.

## Checks that run in CI (`mobile-ci.yml`, job `i18n`)
- `mobile/tools/check_catalogues.sh`: the committed generated Dart matches its JSON (run it locally before committing), and no translation has a key English lacks (the generator drops such keys silently). Keys missing from a translation are listed as a note, not a failure.
- `mobile/tools/i18n_lint`: **no new hardcoded user-visible strings**. It finds string literals passed to `Text(...)`, `title:`, `label:`, `message:`, `hint:`, `tooltip:`, `semanticLabel:` and a few more, in the three apps and the design system, and compares per-file counts with `hardcoded_strings_baseline.json` (832 strings in 107 files when added). A file may keep or reduce its count, never raise it. When you move strings into a catalogue run `dart run bin/check.dart --root ../.. --update` to lower the baseline. It is a ratchet against new strings, not an audit: it does not see every way a string can reach the screen.
