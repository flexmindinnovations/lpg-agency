// Story 2.1: the app's own string catalogue is wired in: typed access,
// English fallback, and the runtime language switch.
import 'package:customer_app/src/i18n/customer_strings.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _app(Locale? locale) => MaterialApp(
  locale: locale,
  supportedLocales: customerLaunchLocales,
  localizationsDelegates: customerLocalizationsDelegates,
  home: Builder(
    builder: (context) =>
        Text('${context.strings.app.title}|${context.lpgStrings.common.retry}'),
  ),
);

void main() {
  test('the catalogue has the app title', () {
    expect(customerStringsFor(const Locale('en')).app.title, 'LPG Agency');
  });

  test('a language the app has no catalogue for gets English', () {
    expect(
      customerStringsFor(const Locale('hi')).app.title,
      customerStringsFor(const Locale('en')).app.title,
    );
    expect(
      customerStringsFor(const Locale('mr', 'IN')).app.title,
      'LPG Agency',
    );
  });

  test('English only at launch', () {
    expect(customerLaunchLocales, const [Locale('en')]);
  });

  testWidgets('the app and shared catalogues reach the widget tree', (
    tester,
  ) async {
    await tester.pumpWidget(_app(null));

    expect(find.text('LPG Agency|Retry'), findsOneWidget);
  });

  testWidgets('a device in another language still gets English', (
    tester,
  ) async {
    await tester.pumpWidget(_app(const Locale('ta')));
    await tester.pumpAndSettle();

    expect(find.text('LPG Agency|Retry'), findsOneWidget);
  });
}
