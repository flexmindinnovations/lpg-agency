# i18n tooling decision (story 0.2)

**Status: recommended, built as a working example; the owner has not signed it off.** Not yet an ADR: the next free number on `main` is ADR-071, but other branches may take it, so the number is allocated when this is promoted (story 2.1 or the release note).

## Decision
Use **slang** (typed JSON catalogues, generated Dart) with `locale_handling: false`, delivered through a small `LocalizationsDelegate` per catalogue. Flutter's own `gen-l10n` (ARB) was the alternative and also meets every requirement; the choice is close, and the reasons are below so it can be reversed cheaply.

Working example: `mobile/packages/design_system` (`slang.yaml`, `lib/src/i18n/*.i18n.json`, generated `strings*.g.dart`, `LpgStringsDelegate`, `test/i18n_test.dart`). Generate with `dart run slang`; the output is committed (like `tokens.dart`) and is stable across runs (no timestamp).

## Versions (checked on pub.dev, 2026-11-05)
| Package | Version | Published |
|---|---|---|
| `slang` | 4.19.2 | 2026-09-12 |
| `slang_flutter` | 4.19.0 | 2026-08-06 |
| `intl` | 0.20.3 (already in use) | 2026-06-25 |
| `flutter_localizations` | bundled with Flutter 3.47.9 | n/a |
| `slang_build_runner` | not used (the CLI `dart run slang` needs no `build_runner`, so it cannot clash with `drift_dev` in `local_storage`) | n/a |

## Requirements against the two tools
Both were run in a scratch project and `slang` in `design_system`. "Tested" means a passing test or a command run here.

| Requirement | slang (chosen) | gen-l10n (ARB) |
|---|---|---|
| JSON file per locale, add a language by adding a file | `en.i18n.json`, `hi.i18n.json` (plain nested JSON). Tested | `en.arb`, `hi.arb` (JSON with `@key` metadata). Tested |
| Typed keys; a wrong key fails the build | `context.lpgStrings.common.retyr` is an analyzer error. Tested | Generated getters; same. Tested in scratch |
| Typed placeholders | `"Updated {time: String}"` in the string itself. Tested | `@key.placeholders` metadata block per message (verbose) |
| Plurals | `one`/`other` keys, CLDR cardinal rule per language. Tested | ICU `{n, plural, ...}` inside a string. Tested in scratch |
| English fallback for a missing key | Yes, generated subclass inherits English. Tested | Yes, template string used; untranslated keys listed in a file. Tested in scratch |
| Runtime locale switch | Through `MaterialApp.locale` via our delegate, so one setting drives our catalogues and Flutter's own widget text. Tested (`en` to `hi` at runtime) | The same, natively |
| `flutter_localizations` for built-in widget text | Added to the delegates list (`lpgLocalizationsDelegates`). Tested (`OK` becomes `ठीक है`) | Natively |
| Indian number and date formats | `intl`, independent of the tool. Tested: `₹12,34,567.50`, `12 Nov 2026`, Hindi and Marathi month names | Same |
| Several catalogues (shared plus one per app) | One generated class per package, with its own delegate; names set by `class_name`/`enum_name` | One generated class per package (`output-class`); the most natural fit |
| Nested namespaces for 600+ strings | Yes (`orders.cylinders`), easy to browse | Flat keys, namespacing by prefix convention |

## Why slang
1. **It matches the owner's decision literally**: plain JSON catalogues, one file per language, nested by feature, with typed placeholders and plurals readable by a translator without learning ICU syntax or ARB metadata.
2. **Nested keys** suit about 600 strings across three apps better than a flat ARB namespace.
3. **Typed parameters live in the string**, not in a separate metadata block that drifts from it.

## Why it was close, and the costs of slang
- gen-l10n is first-party, the format translation vendors and TMS tools import most readily, and its multi-catalogue story is simpler. If translators insist on ARB, slang can read ARB too (`input_file_pattern: .arb`), so the switch is not a rewrite.
- slang is a third-party package (healthy: releases every few weeks; one maintainer-led project). Mitigation: generated code is committed, so a lapse in maintenance does not break builds.
- Setting `locale_handling: false` is what makes several catalogues coexist and lets `MaterialApp.locale` be the single source of truth. It means we own about 40 lines (`LpgStringsDelegate`) that gen-l10n would generate. Each app repeats that pattern for its own catalogue (story 2.1 provides the template).

## Findings that shape the next stories
- **A key that exists only in a translation is silently dropped** at generation (no error). A typo'd key in `hi.i18n.json` is never shown. Story 2.1 adds a check that fails CI on that (`dart run slang analyze`, which writes `_unused_translations.json`, redirected out of the source tree and asserted empty).
- **A key missing from a translation is not an error by design** (English is shown); `dart run slang analyze` lists them in `_missing_translations.json`. CI should print them as a warning, not fail, until a language is declared complete.
- **Languages are compiled in** (`lazy: false`). Deferred loading made the delegate asynchronous and hung the widget tests, and a few hundred strings per language is small.
- **The generated files are format-stable**: `dart format --set-exit-if-changed .` passes with them committed, and re-running the generator produces no diff. Add a "regenerate and `git diff --exit-code`" step to CI in story 2.1.
- **Digits.** `intl` formats Marathi numbers in native Devanagari digits by default and Hindi in Latin digits. `LpgFormat` keeps amounts in Latin digits (`₹12,34,567`) for every language today. **Product decision to confirm with the owner** (not blocking): Latin digits everywhere for money and quantities (recommended: cash, invoices and UPI screens must match what the bank and the printed bill show), or native digits where the language usually uses them.
- **Test data, not translations.** `hi.i18n.json` in `design_system` holds seven strings written as test data to prove the machinery. They have **not** been reviewed by a Hindi speaker or the domain agent. Before any app lists `hi` as a supported language, replace this file with reviewed copy (stories 2.4 to 2.7).

## Not done here (later stories)
App catalogues, moving existing strings, the hardcoded-string lint and the CI drift step (2.1), the language picker and saved choice (2.2), Indian-script font subsets (2.3).
