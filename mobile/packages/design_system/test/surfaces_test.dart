import 'dart:io';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

double _contrast(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  final hi = la > lb ? la : lb;
  final lo = la > lb ? lb : la;
  return (hi + 0.05) / (lo + 0.05);
}

Iterable<LpgThemeVariant> get _variants => LpgThemeVariant.values;

void main() {
  group('solid tonal layers', () {
    test('in dark mode each layer is a lighter solid than the one below', () {
      final c = LpgTheme.colorsFor(LpgThemeVariant.dark);

      expect(
        c.sheet.computeLuminance(),
        greaterThan(c.card.computeLuminance()),
      );
      expect(
        c.card.computeLuminance(),
        greaterThan(c.canvas.computeLuminance()),
      );
    });

    test('in light mode cards and sheets are white on a tinted canvas', () {
      final c = LpgTheme.colorsFor(LpgThemeVariant.light);

      expect(
        c.card.computeLuminance(),
        greaterThan(c.canvas.computeLuminance()),
      );
      expect(c.sheet, c.card);
      expect(c.shadowFor(LpgSurfaceLevel.sheet), isNotEmpty);
    });

    test('every fill is fully opaque, in every variant', () {
      for (final v in _variants) {
        final c = LpgTheme.colorsFor(v);
        for (final level in LpgSurfaceLevel.values) {
          expect(c.surfaceFor(level).a, 1.0, reason: '$v $level');
        }
        for (final color in [c.heroMuted, c.heroSubtle, c.heroTrack]) {
          expect(color.a, 1.0, reason: '$v hero tint');
        }
        for (final tone in LpgTone.values) {
          expect(tone.container(c).a, 1.0, reason: '$v $tone container');
        }
      }
    });

    test('high contrast separates by a 2 px border, not by shadow', () {
      final c = LpgTheme.colorsFor(LpgThemeVariant.highContrast);

      for (final level in [LpgSurfaceLevel.card, LpgSurfaceLevel.sheet]) {
        expect(c.shadowFor(level), isEmpty);
        expect(c.hairlineFor(level).width, 2);
      }
    });

    test('light and dark use a 1 px hairline', () {
      for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
        final c = LpgTheme.colorsFor(v);
        expect(c.hairlineFor(LpgSurfaceLevel.card).width, 1);
        expect(c.hairlineFor(LpgSurfaceLevel.inverse), BorderSide.none);
      }
    });
  });

  group('contrast (WCAG 2.2 AA)', () {
    test('body and secondary text clear 4.5:1 on the canvas and on cards', () {
      for (final v in _variants) {
        final c = LpgTheme.colorsFor(v);
        for (final bg in [c.canvas, c.card, c.sheet]) {
          expect(_contrast(c.textPrimary, bg), greaterThanOrEqualTo(4.5));
          expect(_contrast(c.textSecondary, bg), greaterThanOrEqualTo(4.5));
        }
      }
    });

    test('text on the inverse surface clears 4.5:1', () {
      for (final v in _variants) {
        final c = LpgTheme.colorsFor(v);
        expect(_contrast(c.onInverse, c.inverse), greaterThanOrEqualTo(4.5));
      }
    });

    test('hero text clears 4.5:1 across the whole gradient', () {
      for (final v in _variants) {
        final c = LpgTheme.colorsFor(v);
        for (final stop in c.heroGradient) {
          expect(_contrast(c.onHero, stop), greaterThanOrEqualTo(4.5));
          expect(_contrast(c.heroMuted, stop), greaterThanOrEqualTo(4.5));
        }
      }
    });

    test('status tones on their container: known gaps are pinned, so the set '
        'can only shrink', () {
      // Pre-existing, found by this audit: in the light theme the tone colours
      // (taken from the shared web tokens) are under 4.5:1 as text on their
      // own tinted container. Fixing it means darker shared tokens, which also
      // changes the web dashboard, so it is a decision for story 10.1 (see
      // TASKS.md). Dark and high contrast pass. If a token is darkened this
      // test fails and the entry must be removed from the list.
      const knownBelowAa = {
        LpgThemeVariant.light: {
          LpgTone.accent,
          LpgTone.success,
          LpgTone.warning,
          LpgTone.danger,
          LpgTone.info,
          LpgTone.neutral,
        },
      };
      for (final v in _variants) {
        final c = LpgTheme.colorsFor(v);
        final failing = {
          for (final tone in LpgTone.values)
            if (_contrast(tone.foreground(c), tone.container(c)) < 4.5) tone,
        };

        expect(failing, knownBelowAa[v] ?? <LpgTone>{}, reason: '$v');
      }
    });
  });

  group('LpgSurface', () {
    Future<void> pump(
      WidgetTester tester,
      LpgThemeVariant variant,
      LpgSurfaceLevel level,
    ) => tester.pumpWidget(
      MaterialApp(
        theme: LpgTheme.build(variant),
        home: Center(
          child: LpgSurface(
            level: level,
            padding: const EdgeInsets.all(8),
            child: const SizedBox(width: 40, height: 40),
          ),
        ),
      ),
    );

    BoxDecoration decoration(WidgetTester tester) =>
        tester
                .widget<DecoratedBox>(
                  find
                      .descendant(
                        of: find.byType(LpgSurface),
                        matching: find.byType(DecoratedBox),
                      )
                      .first,
                )
                .decoration
            as BoxDecoration;

    testWidgets('draws its level\'s fill, hairline and shadow', (tester) async {
      await pump(tester, LpgThemeVariant.light, LpgSurfaceLevel.card);
      final colors = LpgTheme.colorsFor(LpgThemeVariant.light);
      final d = decoration(tester);

      expect(d.color, colors.card);
      expect(
        d.border,
        Border.fromBorderSide(colors.hairlineFor(LpgSurfaceLevel.card)),
      );
      expect(d.boxShadow, colors.cardShadow);
      expect(d.borderRadius, LpgRadius.cardRadius);
    });

    testWidgets('a sheet is rounder and floats higher than a card', (
      tester,
    ) async {
      await pump(tester, LpgThemeVariant.dark, LpgSurfaceLevel.sheet);
      final d = decoration(tester);
      final colors = LpgTheme.colorsFor(LpgThemeVariant.dark);

      expect(d.color, colors.sheet);
      expect(d.borderRadius, BorderRadius.circular(LpgRadius.xxl));
      expect(d.boxShadow, colors.floatingShadow);
    });

    testWidgets('follows the high-contrast variant', (tester) async {
      await pump(tester, LpgThemeVariant.highContrast, LpgSurfaceLevel.card);
      final d = decoration(tester);

      expect(d.boxShadow, isEmpty);
      expect((d.border! as Border).top.width, 2);
    });
  });

  group('the theme uses the surface layers', () {
    test('dialogs, sheets and menus use the sheet layer', () {
      for (final v in _variants) {
        final theme = LpgTheme.build(v);
        final sheet = LpgTheme.colorsFor(v).sheet;

        expect(theme.dialogTheme.backgroundColor, sheet);
        expect(theme.bottomSheetTheme.backgroundColor, sheet);
        expect(theme.popupMenuTheme.color, sheet);
      }
    });

    test('snackbars use the inverse layer', () {
      for (final v in _variants) {
        expect(
          LpgTheme.build(v).snackBarTheme.backgroundColor,
          LpgTheme.colorsFor(v).inverse,
        );
      }
    });
  });

  group('no glass', () {
    // The owner's decision: solid surfaces only. This scans the source of the
    // design system and the three apps so it cannot creep back in.
    const allowedTranslucency = {
      // Shadows are translucent by nature; `tint` blends to an opaque colour.
      'theme.dart',
      // Animated brand effects (glints, ripples), not surfaces.
      'lpg_splash.dart',
      'lpg_timeline.dart',
    };

    Iterable<File> sources() sync* {
      final roots = [
        Directory('lib'),
        for (final app in ['admin_app', 'customer_app', 'driver_app'])
          Directory('../../apps/$app/lib'),
      ];
      for (final root in roots) {
        if (!root.existsSync()) continue;
        for (final f in root.listSync(recursive: true)) {
          if (f is File && f.path.endsWith('.dart')) yield f;
        }
      }
    }

    test('no blur anywhere', () {
      final offenders = [
        for (final f in sources())
          if (RegExp(
            r'BackdropFilter|ImageFilter\.blur|ImageFiltered',
          ).hasMatch(f.readAsStringSync()))
            f.path,
      ];

      expect(offenders, isEmpty);
    });

    test('no translucent fills outside the allow-list', () {
      final offenders = [
        for (final f in sources())
          if (!allowedTranslucency.contains(f.uri.pathSegments.last) &&
              RegExp(
                r'withValues\(\s*alpha|withOpacity\(|withAlpha\(',
              ).hasMatch(f.readAsStringSync()))
            f.path,
      ];

      expect(offenders, isEmpty);
    });
  });
}
