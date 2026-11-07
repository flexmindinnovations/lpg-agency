import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('LpgBackdropLook keeps text readable on the page', () {
    for (final variant in LpgThemeVariant.values) {
      test('${variant.name}: secondary text clears 4.5:1 everywhere', () {
        final colors = LpgTheme.colorsFor(variant);
        final look = LpgBackdropLook.of(colors);
        final text = colors.textSecondary;

        // The page, each wash at its full strength, and the worst grain speck
        // on top of the worst of those.
        final surfaces = [look.base, for (final w in look.washes) w.color];
        for (final s in surfaces) {
          expect(
            LpgBackdropLook.contrast(text, s),
            greaterThanOrEqualTo(4.5),
            reason: 'text on $s',
          );
        }
        final worst = surfaces.reduce(
          (a, b) =>
              LpgBackdropLook.contrast(text, a) <
                  LpgBackdropLook.contrast(text, b)
              ? a
              : b,
        );
        final speckled = colors.tint(
          look.speck,
          look.grainStrength,
          over: worst,
        );
        expect(
          LpgBackdropLook.contrast(text, speckled),
          greaterThanOrEqualTo(4.5),
        );
        // Primary text has far more room.
        expect(
          LpgBackdropLook.contrast(colors.textPrimary, speckled),
          greaterThanOrEqualTo(7),
        );
      });
    }

    test('the dark theme has room to show the effect', () {
      final look = LpgBackdropLook.of(LpgTheme.colorsFor(LpgThemeVariant.dark));
      expect(look.grainStrength, greaterThan(0.03));
      for (final w in look.washes) {
        expect(w.color, isNot(look.base));
      }
    });
  });

  group('LpgBackdrop', () {
    Widget host(ThemeData theme, {Widget? child}) => MaterialApp(
      theme: theme,
      home: Scaffold(body: child ?? const Text('page')),
    );

    Finder painter() => find.descendant(
      of: find.byType(LpgBackdrop),
      matching: find.byType(CustomPaint),
    );

    testWidgets('sits under a routed screen and does not take touches', (
      tester,
    ) async {
      await tester.pumpWidget(host(LpgTheme.light));
      await tester.pumpAndSettle();

      expect(find.byType(LpgBackdrop), findsOneWidget);
      expect(painter(), findsWidgets);
      expect(find.text('page'), findsOneWidget);
      // Decorative: no semantics of its own.
      final semantics = tester.ensureSemantics();
      expect(find.bySemanticsLabel(RegExp('.+')), findsOneWidget);
      semantics.dispose();
    });

    testWidgets('the scaffold lets the page show through', (tester) async {
      expect(LpgTheme.light.scaffoldBackgroundColor, Colors.transparent);
      expect(LpgTheme.dark.scaffoldBackgroundColor, Colors.transparent);
    });

    test('the see-through header keeps legible status bar icons', () {
      // Left to itself Flutter judges the icons from a transparent colour and
      // picks white ones, which vanish on the light page.
      expect(
        LpgTheme.light.appBarTheme.systemOverlayStyle,
        SystemUiOverlayStyle.dark,
      );
      expect(
        LpgTheme.dark.appBarTheme.systemOverlayStyle,
        SystemUiOverlayStyle.light,
      );
    });

    testWidgets('in high contrast the page is a plain colour', (tester) async {
      await tester.pumpWidget(host(LpgTheme.highContrast));
      await tester.pumpAndSettle();

      expect(painter(), findsNothing);
      final fill = tester.widget<ColoredBox>(
        find
            .descendant(
              of: find.byType(LpgBackdrop),
              matching: find.byType(ColoredBox),
            )
            .first,
      );
      expect(
        fill.color,
        LpgTheme.colorsFor(LpgThemeVariant.highContrast).canvas,
      );
    });

    testWidgets('a pushed page brings its own backdrop and stays opaque', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.light,
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const Scaffold(body: Text('second')),
                  ),
                ),
                child: const Text('go'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('go'));
      await tester.pumpAndSettle();

      expect(find.byType(LpgBackdrop, skipOffstage: false), findsNWidgets(2));
      expect(find.text('second'), findsOneWidget);
    });

    testWidgets('under reduce-motion the page is still drawn', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.build(LpgThemeVariant.light, reduceMotion: true),
          home: const Scaffold(body: Text('page')),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(LpgBackdrop), findsOneWidget);
    });
  });
}
