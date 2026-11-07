import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

double _contrast(Color a, Color b) => LpgBackdropLook.contrast(a, b);

Future<void> _pump(
  WidgetTester tester,
  LpgThemeVariant variant,
  Widget child,
) => tester.pumpWidget(
  MaterialApp(
    theme: LpgTheme.build(variant),
    home: Scaffold(body: Center(child: child)),
  ),
);

void main() {
  group('LpgGlassLook', () {
    test('high contrast is fully opaque', () {
      final look = LpgGlassLook.of(
        LpgTheme.colorsFor(LpgThemeVariant.highContrast),
      );

      expect(look.cardAlpha, 1);
      expect(look.sheetAlpha, 1);
    });

    test('light and dark are genuinely see-through', () {
      for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
        final look = LpgGlassLook.of(LpgTheme.colorsFor(v));

        // A card, field or chip is 60% opaque: the paper's grain shows
        // through softly, and text stays readable on it.
        expect(
          look.cardAlpha,
          inInclusiveRange(LpgGlassLook.cardTarget, 0.95),
          reason: '$v card',
        );
        expect(
          look.sheetAlpha,
          inInclusiveRange(LpgGlassLook.sheetTarget, 1.0),
          reason: '$v sheet',
        );
      }
    });

    test('text on a card is as readable as on the page, worst pixel included', () {
      for (final v in LpgThemeVariant.values) {
        final c = LpgTheme.colorsFor(v);
        final page = LpgBackdropLook.of(c);
        final behind = [
          c.canvas,
          page.base,
        ].map((b) => c.tint(page.speck, page.grainStrength, over: b));

        for (final back in behind) {
          // A card has no grain of its own: the page's shows through.
          final glass = Color.alphaBlend(
            c.cardGlass,
            back,
          );
          expect(
            _contrast(c.textPrimary, glass),
            greaterThanOrEqualTo(LpgGlassLook.cardContrast - 0.01),
            reason: '$v primary',
          );
          expect(
            _contrast(c.textSecondary, glass),
            greaterThanOrEqualTo(LpgGlassLook.cardContrast - 0.01),
            reason: '$v secondary',
          );
        }
      }
    });

    test(
      'a bar keeps AA text contrast',
      () {
        for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
          final c = LpgTheme.colorsFor(v);
          final page = LpgBackdropLook.of(c);
          expect(
            LpgGlassLook.of(c).barAlpha,
            inInclusiveRange(LpgGlassLook.barTarget, 1.0),
          );

          for (final w in [c.canvas, page.base]) {
            final back = c.tint(
              page.speck,
              LpgGlassLook.grainStrength,
              over: w,
            );
            final bar = Color.alphaBlend(c.barGlass, back);
            expect(
              _contrast(c.textPrimary, bar),
              greaterThanOrEqualTo(4.5),
              reason: '$v',
            );
            expect(
              _contrast(c.textSecondary, bar),
              greaterThanOrEqualTo(4.5),
              reason: '$v',
            );
          }
        }
      },
    );

    test(
      'card outlines and row dividers are a clear step darker than the card',
      () {
        for (final v in [LpgThemeVariant.light]) {
          final c = LpgTheme.colorsFor(v);
          expect(_contrast(c.outline, c.card), greaterThanOrEqualTo(1.6));
          expect(_contrast(c.rowDivider, c.card), greaterThanOrEqualTo(1.4));
        }
      },
    );

    test('text on a frosted sheet stays at 6:1 over black or white '
        'content, the extremes a blur can average to', () {
      for (final v in LpgThemeVariant.values) {
        final c = LpgTheme.colorsFor(v);
        final page = LpgBackdropLook.of(c);
        // A fully opaque sheet cannot be made any more readable: it is then
        // just the theme's own sheet colour, held to AA by the theme itself.
        final floor = LpgGlassLook.of(c).sheetAlpha >= 1
            ? LpgBackdropLook.minTextContrast
            : LpgGlassLook.readableContrast - 0.01;
        for (final back in const [Color(0xFF000000), Color(0xFFFFFFFF)]) {
          final glass = Color.alphaBlend(
            c.sheetGlass,
            c.tint(page.speck, LpgGlassLook.sheetGrainStrength, over: back),
          );
          expect(
            _contrast(c.textSecondary, glass),
            greaterThanOrEqualTo(floor),
            reason: '$v over $back',
          );
          expect(
            _contrast(c.textPrimary, glass),
            greaterThanOrEqualTo(floor),
            reason: '$v over $back',
          );
        }
      }
    });
  });

  group('LpgGlass', () {
    testWidgets('blurs what is behind it, in light and dark', (tester) async {
      for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
        await _pump(tester, v, const LpgGlass(child: SizedBox(width: 80)));

        expect(find.byType(BackdropFilter), findsOneWidget, reason: '$v');
      }
    });

    testWidgets('blur can be left off', (tester) async {
      await _pump(
        tester,
        LpgThemeVariant.light,
        const LpgGlass(blur: false, child: SizedBox(width: 80)),
      );

      expect(find.byType(BackdropFilter), findsNothing);
    });

    testWidgets('is a solid surface, with no blur, in high contrast', (
      tester,
    ) async {
      await _pump(
        tester,
        LpgThemeVariant.highContrast,
        const LpgGlass(child: SizedBox(width: 80)),
      );

      expect(find.byType(BackdropFilter), findsNothing);
      final box = tester.widget<DecoratedBox>(
        find
            .descendant(
              of: find.byType(LpgSurface),
              matching: find.byType(DecoratedBox),
            )
            .first,
      );
      expect((box.decoration as BoxDecoration).color!.a, 1.0);
    });
  });

  group('cards', () {
    Color fillOf(WidgetTester tester) => tester
        .widget<Material>(
          find
              .descendant(
                of: find.byType(LpgCard),
                matching: find.byType(Material),
              )
              .first,
        )
        .color!;

    testWidgets('are see-through and not blurred', (tester) async {
      for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
        await _pump(tester, v, const LpgCard(child: Text('Order 1042')));

        expect(fillOf(tester).a, lessThan(1), reason: '$v');
        // A backdrop blur per card, redrawn every frame of a scroll, is what
        // made lists drop frames.
        expect(find.byType(BackdropFilter), findsNothing, reason: '$v');
        expect(find.byType(LpgGlassPane), findsNothing, reason: '$v');
      }
    });

    testWidgets('a surface card is the same glass as a card', (tester) async {
      await _pump(
        tester,
        LpgThemeVariant.light,
        const LpgSurface(child: Text('Panel')),
      );

      expect(find.byType(BackdropFilter), findsNothing);
      expect(find.byType(LpgGlassPane), findsNothing);
    });

    testWidgets('are opaque in high contrast, with no blur or grain', (
      tester,
    ) async {
      await _pump(
        tester,
        LpgThemeVariant.highContrast,
        const LpgCard(child: Text('Order 1042')),
      );

      expect(fillOf(tester).a, 1.0);
      expect(find.byType(BackdropFilter), findsNothing);
      expect(find.byType(LpgGlassPane), findsNothing);
    });

    testWidgets('a tonal card stays an opaque tint', (tester) async {
      await _pump(
        tester,
        LpgThemeVariant.light,
        const LpgCard(variant: LpgCardVariant.tonal, child: Text('Note')),
      );

      expect(fillOf(tester).a, 1.0);
    });
  });

  group('bottom sheet', () {
    Future<void> open(WidgetTester tester, LpgThemeVariant variant) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.build(variant),
          home: Builder(
            builder: (context) => Scaffold(
              body: Center(
                child: TextButton(
                  onPressed: () => LpgFeedback.showSheet<void>(
                    context,
                    title: 'Deliver order',
                    builder: (_) => const Text('Body'),
                  ),
                  child: const Text('Open'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();
    }

    for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
      testWidgets('is frosted glass in ${v.name}', (tester) async {
        await open(tester, v);

        expect(find.byType(BackdropFilter), findsOneWidget);
        expect(find.text('Deliver order'), findsOneWidget);
        expect(find.text('Body'), findsOneWidget);
        expect(find.byType(LpgSheetHandle), findsOneWidget);
      });
    }

    testWidgets('is solid in high contrast', (tester) async {
      await open(tester, LpgThemeVariant.highContrast);

      expect(find.byType(BackdropFilter), findsNothing);
      expect(find.text('Deliver order'), findsOneWidget);
    });

    testWidgets('the handle closes the sheet', (tester) async {
      await open(tester, LpgThemeVariant.light);

      await tester.tap(find.byType(LpgSheetHandle));
      await tester.pumpAndSettle();

      expect(find.text('Deliver order'), findsNothing);
    });
  });
}
