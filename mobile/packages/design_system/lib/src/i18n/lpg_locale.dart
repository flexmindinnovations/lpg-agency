import 'package:flutter/foundation.dart' show SynchronousFuture;
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:riverpod/riverpod.dart';

/// Delivers one generated catalogue (`AdminStrings`, `CustomerStrings`, ...)
/// to the widget tree through Flutter's normal localisation machinery, so a
/// single setting (`MaterialApp.locale`) switches every catalogue and Flutter's
/// own widget text together.
///
/// [resolve] maps the requested [Locale] to the catalogue; it must fall back to
/// English for a language the catalogue does not have, so a missing
/// translation file never breaks a screen. Generated catalogues are compiled
/// in (`lazy: false`), so loading is synchronous and never delays a frame.
class LpgCatalogueDelegate<S> extends LocalizationsDelegate<S> {
  const LpgCatalogueDelegate(this.resolve);

  final S Function(Locale locale) resolve;

  @override
  bool isSupported(Locale locale) => true;

  @override
  Future<S> load(Locale locale) => SynchronousFuture<S>(resolve(locale));

  @override
  bool shouldReload(LpgCatalogueDelegate<S> old) => false;
}

/// Flutter's built-in widget text (date pickers, dialogs, back button) for
/// every language Flutter ships.
List<LocalizationsDelegate<dynamic>> get lpgFlutterDelegates =>
    GlobalMaterialLocalizations.delegates;

/// The app's chosen language, or `null` to follow the device. Switching it
/// rebuilds `MaterialApp` with the new `locale`. Saving the choice per device
/// and the language picker are story 2.2.
class LpgLocaleNotifier extends Notifier<Locale?> {
  @override
  Locale? build() => null;

  /// Switch to [locale]; `null` follows the device again.
  void select(Locale? locale) => state = locale;
}

final lpgLocaleProvider = NotifierProvider<LpgLocaleNotifier, Locale?>(
  LpgLocaleNotifier.new,
);
