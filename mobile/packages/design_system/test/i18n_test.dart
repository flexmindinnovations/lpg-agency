// Story 0.2 spike: what the chosen i18n tooling must do, proven on the design
// system's own catalogue (en.i18n.json, plus hi.i18n.json as a test locale).
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:intl/intl.dart';

/// One `MaterialApp` whose language can be changed while it runs, the way a
/// language picker will.
Widget _app(ValueNotifier<Locale> locale) => ValueListenableBuilder<Locale>(
  valueListenable: locale,
  builder: (context, value, _) => _materialApp(value),
);

/// Shows a few strings from [LpgStrings] plus Flutter's own `OK` label, in
/// whatever [locale] the app is currently set to.
Widget _materialApp(Locale locale) => MaterialApp(
  locale: locale,
  supportedLocales: lpgSupportedLocales,
  localizationsDelegates: lpgLocalizationsDelegates,
  home: Builder(
    builder: (context) {
      final s = context.lpgStrings;
      return Column(
        children: [
          Text(s.common.retry),
          Text(s.async.lastUpdated(time: '10:30')),
          Text(s.stock.cylinders(n: 1)),
          Text(s.stock.cylinders(n: 12)),
          Text(s.stock.onlyInEnglish),
          Text(MaterialLocalizations.of(context).okButtonLabel),
        ],
      );
    },
  ),
);

void main() {
  testWidgets('English is the base: values, placeholders, plurals', (
    tester,
  ) async {
    await tester.pumpWidget(_app(ValueNotifier(const Locale('en'))));

    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('Updated 10:30'), findsOneWidget);
    expect(find.text('1 cylinder'), findsOneWidget);
    expect(find.text('12 cylinders'), findsOneWidget);
    expect(find.text('OK'), findsOneWidget);
  });

  testWidgets('switching the app locale at runtime switches both the '
      'catalogue and the built-in widget text', (tester) async {
    final locale = ValueNotifier(const Locale('en'));
    await tester.pumpWidget(_app(locale));
    expect(find.text('Retry'), findsOneWidget);

    locale.value = const Locale('hi');
    await tester.pumpAndSettle();

    expect(find.text('फिर कोशिश करें'), findsOneWidget);
    expect(find.text('10:30 को अपडेट किया'), findsOneWidget);
    expect(find.text('1 सिलेंडर'), findsOneWidget);
    expect(find.text('12 सिलेंडर'), findsOneWidget);
    // Flutter's own string, from flutter_localizations, not from our catalogue.
    expect(find.text('OK'), findsNothing);
    expect(find.text('ठीक है'), findsOneWidget);
  });

  testWidgets('a key missing from a language falls back to English', (
    tester,
  ) async {
    await tester.pumpWidget(_app(ValueNotifier(const Locale('hi'))));
    await tester.pumpAndSettle();

    expect(find.text('This line exists only in English.'), findsOneWidget);
  });

  testWidgets('a language with no catalogue resolves to English', (
    tester,
  ) async {
    await tester.pumpWidget(_app(ValueNotifier(const Locale('mr'))));
    await tester.pumpAndSettle();

    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('12 cylinders'), findsOneWidget);
  });

  test(
    'typed access: a translation differs from English only in its text',
    () async {
      final en = LpgLocale.en.buildSync();
      final hi = LpgLocale.hi.buildSync();
      expect(hi.common.retry, isNot(en.common.retry));
      expect(hi.stock.onlyInEnglish, en.stock.onlyInEnglish);
    },
  );

  group('Indian formats come from intl, per locale', () {
    setUpAll(() async {
      await initializeDateFormatting('hi_IN');
      await initializeDateFormatting('mr_IN');
    });

    test('rupees use lakh and crore grouping', () {
      expect(LpgFormat.currency(1234567.5), '₹12,34,567.50');
      expect(LpgFormat.currencyWhole(12345678), '₹1,23,45,678');
    });

    test('grouping is Indian in every Indian locale; Marathi defaults to '
        'native digits, Hindi to Latin', () {
      expect(NumberFormat.decimalPattern('en_IN').format(1234567), '12,34,567');
      expect(NumberFormat.decimalPattern('hi_IN').format(1234567), '12,34,567');
      // Product choice still open (see i18n-decision.md): intl's own default
      // for Marathi is native digits. LpgFormat keeps amounts in Latin digits
      // for every language.
      expect(NumberFormat.decimalPattern('mr_IN').format(1234567), '१२,३४,५६७');
    });

    test('dates are written in the language of the locale', () {
      final day = DateTime(2026, 11, 12);
      expect(DateFormat.yMMMd('en_IN').format(day), '12 Nov 2026');
      expect(DateFormat.yMMMd('hi_IN').format(day), contains('नव'));
      expect(DateFormat.yMMMd('mr_IN').format(day), contains('नोव्हें'));
    });
  });
}
