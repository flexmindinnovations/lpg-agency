import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:riverpod/riverpod.dart';

void main() {
  group('LpgThemeModeController', () {
    test('parses what it saved and falls back to the phone for the rest', () {
      expect(LpgThemeModeController.parse('dark'), ThemeMode.dark);
      expect(LpgThemeModeController.parse('light'), ThemeMode.light);
      expect(LpgThemeModeController.parse('system'), ThemeMode.system);
      expect(LpgThemeModeController.parse(null), ThemeMode.system);
      expect(LpgThemeModeController.parse('purple'), ThemeMode.system);
    });

    test('load restores the saved choice', () async {
      final c = await LpgThemeModeController.load(
        read: () async => 'dark',
        write: (_) async {},
      );
      expect(c.value, ThemeMode.dark);
    });

    test('load follows the phone when storage fails', () async {
      final c = await LpgThemeModeController.load(
        read: () async => throw StateError('keystore unavailable'),
        write: (_) async {},
      );
      expect(c.value, ThemeMode.system);
    });

    test('select applies at once and saves the name', () async {
      final saved = <String>[];
      final c = LpgThemeModeController(write: (v) async => saved.add(v));
      var notified = 0;
      c.addListener(() => notified++);

      c.select(ThemeMode.dark);
      c.select(ThemeMode.dark); // no change, nothing more to do
      await Future<void>.delayed(Duration.zero);

      expect(c.value, ThemeMode.dark);
      expect(notified, 1);
      expect(saved, ['dark']);
    });

    test('a failed save still applies the choice', () async {
      final c = LpgThemeModeController(
        write: (_) async => throw StateError('disk full'),
      );
      c.select(ThemeMode.light);
      await Future<void>.delayed(Duration.zero);
      expect(c.value, ThemeMode.light);
    });

    test('the provider follows the controller', () {
      final controller = LpgThemeModeController();
      final container = ProviderContainer(
        overrides: [
          lpgThemeModeControllerProvider.overrideWithValue(controller),
        ],
      );
      addTearDown(container.dispose);

      expect(container.read(lpgThemeModeProvider), ThemeMode.system);
      controller.select(ThemeMode.dark);
      expect(container.read(lpgThemeModeProvider), ThemeMode.dark);
    });
  });

  group('LpgThemeModePicker', () {
    Widget host(LpgThemeModeController c) => MaterialApp(
      theme: LpgTheme.light,
      localizationsDelegates: [
        const LpgStringsDelegate(),
        ...lpgFlutterDelegates,
      ],
      home: Scaffold(body: LpgThemeModePicker(controller: c)),
    );

    testWidgets('shows the three choices and changes the mode on a tap', (
      tester,
    ) async {
      final controller = LpgThemeModeController();
      await tester.pumpWidget(host(controller));

      expect(find.text('Appearance'), findsOneWidget);
      expect(find.text('Match phone'), findsOneWidget);
      expect(find.text('Light'), findsOneWidget);

      await tester.tap(find.text('Dark'));
      await tester.pump();
      expect(controller.value, ThemeMode.dark);
      expect(
        tester
            .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Dark'))
            .selected,
        isTrue,
      );
    });

    testWidgets('tapping the chosen mode does not clear it', (tester) async {
      final controller = LpgThemeModeController(initial: ThemeMode.light);
      await tester.pumpWidget(host(controller));

      await tester.tap(find.text('Light'));
      await tester.pump();
      expect(controller.value, ThemeMode.light);
    });
  });
}
