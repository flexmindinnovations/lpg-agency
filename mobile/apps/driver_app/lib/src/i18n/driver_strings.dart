import 'package:design_system/design_system.dart';
import 'package:flutter/widgets.dart';

import 'strings.g.dart';

export 'strings.g.dart' show DriverLocale, DriverStrings;

/// The languages this app ships. **English only at launch** (owner's decision):
/// a device set to another language still gets English. To add a language,
/// add its `<code>.i18n.json` here, run `dart run slang`, and list it below
/// (see planning/features/61-mobile-ui-revamp/i18n-howto.md).
const driverLaunchLocales = [Locale('en')];

/// The catalogue for [locale]: its language if the app has one, otherwise
/// English.
DriverStrings driverStringsFor(Locale locale) =>
    AppLocaleUtils.parseLocaleParts(
      languageCode: locale.languageCode,
      scriptCode: locale.scriptCode,
      countryCode: locale.countryCode,
    ).buildSync();

/// Everything `MaterialApp.localizationsDelegates` needs: this app's
/// catalogue, the shared design-system catalogue and Flutter's own widget text.
final driverLocalizationsDelegates = <LocalizationsDelegate<dynamic>>[
  const LpgCatalogueDelegate<DriverStrings>(driverStringsFor),
  const LpgStringsDelegate(),
  ...lpgFlutterDelegates,
];

/// `context.strings.app.title`
extension DriverStringsContext on BuildContext {
  DriverStrings get strings =>
      Localizations.of<DriverStrings>(this, DriverStrings)!;
}
