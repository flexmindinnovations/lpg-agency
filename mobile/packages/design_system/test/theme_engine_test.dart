import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Pumps a `MaterialApp` wired the way every app wires the engine, at
/// [size] and with the platform's [textScale] and [platformReduceMotion].
Future<BuildContext> _pump(
  WidgetTester tester, {
  LpgThemeEngine engine = const LpgThemeEngine(),
  Size size = const Size(400, 800),
  double textScale = 1.0,
  bool platformReduceMotion = false,
  ThemeMode themeMode = ThemeMode.light,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  late BuildContext captured;
  await tester.pumpWidget(
    MediaQuery(
      data: MediaQueryData(
        size: size,
        textScaler: TextScaler.linear(textScale),
        disableAnimations: platformReduceMotion,
      ),
      child: MaterialApp(
        theme: engine.light,
        darkTheme: engine.dark,
        highContrastTheme: engine.highContrast,
        themeMode: themeMode,
        builder: engine.builder,
        home: Builder(
          builder: (context) {
            captured = context;
            return const SizedBox();
          },
        ),
      ),
    ),
  );
  return captured;
}

void main() {
  group('variants', () {
    test('light, dark and high contrast come from the same tokens', () {
      const engine = LpgThemeEngine();

      expect(engine.light.brightness, Brightness.light);
      expect(engine.dark.brightness, Brightness.dark);
      expect(engine.highContrast.brightness, Brightness.light);
      final hc = engine.highContrast.extension<LpgColors>()!;
      expect(hc.isHighContrast, isTrue);
    });

    test('the default engine matches the plain LpgTheme (no behaviour change '
        'for the apps)', () {
      const engine = LpgThemeEngine();
      for (final variant in LpgThemeVariant.values) {
        final plain = LpgTheme.colorsFor(variant);
        final built = switch (variant) {
          LpgThemeVariant.light => engine.light,
          LpgThemeVariant.dark => engine.dark,
          LpgThemeVariant.highContrast => engine.highContrast,
        }.extension<LpgColors>()!;
        expect(built.accent, plain.accent, reason: '$variant');
        expect(built.actionPrimary, plain.actionPrimary, reason: '$variant');
        expect(built.card, plain.card, reason: '$variant');
      }
    });
  });

  group('accent', () {
    test('the app accent reaches the colours and the colour scheme', () {
      const engine = LpgThemeEngine(accent: LpgAccent.gas);

      for (final variant in LpgThemeVariant.values) {
        final theme = switch (variant) {
          LpgThemeVariant.light => engine.light,
          LpgThemeVariant.dark => engine.dark,
          LpgThemeVariant.highContrast => engine.highContrast,
        };
        final expected = LpgAccent.gas.forVariant(variant);
        expect(theme.extension<LpgColors>()!.accent, expected);
        expect(theme.colorScheme.secondary, expected);
      }
    });

    test('the accent never changes the structural primary colour', () {
      expect(
        const LpgThemeEngine(
          accent: LpgAccent.gas,
        ).light.extension<LpgColors>()!.actionPrimary,
        const LpgThemeEngine().light.extension<LpgColors>()!.actionPrimary,
      );
    });
  });

  group('text scale', () {
    testWidgets('follows the person up to the engine limit and no further', (
      tester,
    ) async {
      var context = await _pump(tester, textScale: 1.5);
      expect(MediaQuery.textScalerOf(context).scale(10), 15);

      context = await _pump(tester, textScale: 3.0);
      expect(MediaQuery.textScalerOf(context).scale(10), 20);
    });

    testWidgets('the limit is configurable per app', (tester) async {
      final context = await _pump(
        tester,
        engine: const LpgThemeEngine(maxTextScale: 1.5),
        textScale: 3.0,
      );
      expect(MediaQuery.textScalerOf(context).scale(10), 15);
    });

    testWidgets('LpgTextScaleLimit caps a fixed layout without touching the '
        'rest', (tester) async {
      late BuildContext inside;
      late BuildContext outside;
      const engine = LpgThemeEngine();
      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(2.0)),
          child: MaterialApp(
            theme: engine.light,
            builder: engine.builder,
            home: Builder(
              builder: (c) {
                outside = c;
                return LpgTextScaleLimit(
                  child: Builder(
                    builder: (c) {
                      inside = c;
                      return const SizedBox();
                    },
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(MediaQuery.textScalerOf(inside).scale(10), 13);
      expect(MediaQuery.textScalerOf(outside).scale(10), 20);
    });
  });

  group('density by size class', () {
    testWidgets('a phone keeps today\'s spacing exactly', (tester) async {
      final context = await _pump(tester, size: const Size(400, 800));
      final density = context.lpgDensity;

      expect(density.sizeClass, LpgSizeClass.compact);
      expect(density.pageGutter, LpgSpacing.mdl);
      expect(density.cardPadding, LpgSpacing.mdl);
    });

    testWidgets('wider windows step up', (tester) async {
      var context = await _pump(tester, size: const Size(700, 900));
      expect(context.lpgDensity.sizeClass, LpgSizeClass.medium);
      final medium = context.lpgDensity.pageGutter;

      context = await _pump(tester, size: const Size(1100, 800));
      expect(context.lpgDensity.sizeClass, LpgSizeClass.expanded);
      expect(context.lpgDensity.pageGutter, greaterThan(medium));
      expect(medium, greaterThan(LpgSpacing.mdl));
    });

    test('size classes follow the Material 3 breakpoints', () {
      expect(LpgSizeClass.fromWidth(599), LpgSizeClass.compact);
      expect(LpgSizeClass.fromWidth(600), LpgSizeClass.medium);
      expect(LpgSizeClass.fromWidth(839), LpgSizeClass.medium);
      expect(LpgSizeClass.fromWidth(840), LpgSizeClass.expanded);
    });

    testWidgets('a bare MaterialApp falls back to the phone density', (
      tester,
    ) async {
      late BuildContext context;
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (c) {
              context = c;
              return const SizedBox();
            },
          ),
        ),
      );
      expect(context.lpgDensity.sizeClass, LpgSizeClass.compact);
    });
  });

  group('reduce motion', () {
    testWidgets('off by default: pages animate, durations are normal', (
      tester,
    ) async {
      final context = await _pump(tester);

      expect(MediaQuery.disableAnimationsOf(context), isFalse);
      expect(LpgMotion.medium(context), LpgTokens.motionDurationMedium);
      expect(
        Theme.of(context).pageTransitionsTheme,
        isNot(same(lpgInstantPageTransitions)),
      );
    });

    testWidgets('the platform setting collapses motion', (tester) async {
      final context = await _pump(tester, platformReduceMotion: true);

      expect(MediaQuery.disableAnimationsOf(context), isTrue);
      expect(
        LpgMotion.medium(context),
        LpgTokens.motionReducedMotionDurationMedium,
      );
      expect(
        Theme.of(context).pageTransitionsTheme,
        same(lpgInstantPageTransitions),
      );
    });

    testWidgets('the engine flag forces it on regardless of the platform', (
      tester,
    ) async {
      final context = await _pump(
        tester,
        engine: const LpgThemeEngine(reduceMotion: true),
      );

      expect(MediaQuery.disableAnimationsOf(context), isTrue);
      expect(
        Theme.of(context).pageTransitionsTheme,
        same(lpgInstantPageTransitions),
      );
    });
  });
}
