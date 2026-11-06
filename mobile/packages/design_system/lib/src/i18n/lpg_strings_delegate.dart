import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'strings.g.dart';

/// Delivers the design system's own catalogue ([LpgStrings]) to the widget
/// tree through Flutter's normal localisation machinery, so one setting
/// (`MaterialApp.locale`) switches this catalogue, every app catalogue and
/// Flutter's built-in widget text together.
///
/// An unsupported language resolves to English, so a missing translation file
/// never breaks a screen. A *key* missing from a supported language also falls
/// back to English (the generator's `fallback_strategy: base_locale`).
class LpgStringsDelegate extends LocalizationsDelegate<LpgStrings> {
  const LpgStringsDelegate();

  @override
  bool isSupported(Locale locale) => true;

  @override
  Future<LpgStrings> load(Locale locale) {
    final match = LpgLocale.values.where(
      (l) => l.languageCode == locale.languageCode,
    );
    final resolved = match.isEmpty ? LpgLocale.en : match.first;
    return SynchronousFuture(resolved.buildSync());
  }

  @override
  bool shouldReload(LpgStringsDelegate old) => false;
}

/// The languages the design system has a catalogue for.
List<Locale> get lpgSupportedLocales => [
  for (final l in LpgLocale.values) l.flutterLocale,
];

/// Everything an app passes to `MaterialApp.localizationsDelegates` for the
/// shared catalogue plus Flutter's built-in widget text.
const lpgLocalizationsDelegates = <LocalizationsDelegate<dynamic>>[
  LpgStringsDelegate(),
  ...GlobalMaterialLocalizations.delegates,
];

/// `context.lpgStrings.common.retry`
extension LpgStringsContext on BuildContext {
  /// English when no [LpgStringsDelegate] is above (a bare `MaterialApp` in a
  /// test or a preview), so a shared widget never fails for a missing setup.
  LpgStrings get lpgStrings =>
      Localizations.of<LpgStrings>(this, LpgStrings) ??
      LpgLocale.en.buildSync();
}
