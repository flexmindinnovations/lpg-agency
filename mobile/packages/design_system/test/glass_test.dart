import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

double _contrast(Color a, Color b) => LpgBackdropLook.contrast(a, b);

/// The page's paper inside [parent]. (The app's own page is one outside it.)
Finder _paperIn(Type parent) => find.descendant(
  of: find.byType(parent),
  matching: find.byType(LpgBackdrop),
);

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
      expect(look.barAlpha, 1);
      expect(look.sheetAlpha, 1);
    });

    test('light and dark are genuinely see-through', () {
      for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
        final look = LpgGlassLook.of(LpgTheme.colorsFor(v));

        // A card, field or chip is 30% opaque: the page's paper shows
        // through softly, and text stays readable on it.
        expect(
          look.cardAlpha,
          inInclusiveRange(LpgGlassLook.cardTarget, 0.95),
          reason: '$v card',
        );
      }
    });

    test(
      'text on a card is as readable as on the page, worst pixel included',
      () {
        for (final v in LpgThemeVariant.values) {
          final c = LpgTheme.colorsFor(v);
          final page = LpgBackdropLook.of(c);
          final behind = [
            c.canvas,
            ...page.samples,
          ].map((b) => c.tint(page.speck, page.grainStrength, over: b));

          for (final back in behind) {
            // A card has no texture of its own: the page's shows through.
            final glass = Color.alphaBlend(c.cardGlass, back);
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
      },
    );

    test('a sheet shows the blurred screen, and its text holds over the worst '
        'colours that can be blurred behind it', () {
      for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
        final c = LpgTheme.colorsFor(v);
        final alpha = LpgGlassLook.of(c).sheetAlpha;
        expect(
          alpha,
          inInclusiveRange(LpgGlassLook.sheetTarget, 1.0),
          reason: '$v',
        );
        // Not (nearly) opaque: some of the screen behind has to show.
        expect(alpha, lessThan(0.9), reason: '$v');

        for (final back in LpgGlassLook.sheetBackdrops(c, [c.canvas])) {
          // The paper's grain is over the tint and under the text.
          final page = LpgBackdropLook.of(c);
          final sheet = c.tint(
            page.speck,
            page.grainStrength * LpgBackdropLook.overlayShare,
            over: Color.alphaBlend(c.sheetGlass, back),
          );
          for (final text in [c.textPrimary, c.textSecondary]) {
            expect(
              _contrast(text, sheet),
              greaterThanOrEqualTo(LpgGlassLook.sheetContrast - 0.01),
              reason: '$v over $back',
            );
          }
        }
      }
    });

    test('a bar keeps AA text contrast', () {
      for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
        final c = LpgTheme.colorsFor(v);
        final page = LpgBackdropLook.of(c);
        expect(
          LpgGlassLook.of(c).barAlpha,
          inInclusiveRange(LpgGlassLook.barTarget, 1.0),
        );

        for (final w in [c.canvas, ...page.samples]) {
          final back = c.tint(page.speck, page.grainStrength, over: w);
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
    });

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
  });

  group('LpgGlass', () {
    testWidgets('a card-level glass is not blurred, in light and dark', (
      tester,
    ) async {
      for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
        await _pump(
          tester,
          v,
          const LpgGlass(
            level: LpgSurfaceLevel.card,
            child: SizedBox(width: 80),
          ),
        );

        expect(find.byType(BackdropFilter), findsNothing, reason: '$v');
        expect(_paperIn(LpgGlass), findsNothing, reason: '$v');
      }
    });

    testWidgets(
      'a sheet-level glass is frosted with no border, not blurred live',
      (tester) async {
        for (final v in [LpgThemeVariant.light, LpgThemeVariant.dark]) {
          await _pump(tester, v, const LpgGlass(child: SizedBox(width: 80)));

          // The paper under the blurred picture (it shows until the picture
          // arrives) and its grain over the picture: two layers of the page's
          // own painter.
          expect(_paperIn(LpgGlass), findsNWidgets(2), reason: '$v');
          expect(
            tester
                .widgetList<LpgBackdrop>(_paperIn(LpgGlass))
                .where((b) => b.overlay),
            hasLength(1),
            reason: '$v: grain over the glass',
          );
          expect(find.byType(BackdropFilter), findsNothing, reason: '$v');
          final borders = tester
              .widgetList<DecoratedBox>(
                find.descendant(
                  of: find.byType(LpgGlass),
                  matching: find.byType(DecoratedBox),
                ),
              )
              .where((b) => (b.decoration as BoxDecoration).border != null);
          expect(borders, isEmpty, reason: '$v: no sheet border');
        }
      },
    );

    testWidgets('is a solid surface, with no paper, in high contrast', (
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
        // No texture of its own: the page's paper is what shows through.
        expect(_paperIn(LpgCard), findsNothing, reason: '$v');
      }
    });

    testWidgets('a surface card is the same glass as a card', (tester) async {
      await _pump(
        tester,
        LpgThemeVariant.light,
        const LpgSurface(child: Text('Panel')),
      );

      expect(find.byType(BackdropFilter), findsNothing);
      expect(_paperIn(LpgSurface), findsNothing);
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

  group('glass snapshot', () {
    testWidgets('is a small blurred picture of the app, made once', (
      tester,
    ) async {
      late BuildContext inside;
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.light,
          home: LpgGlassSource(
            child: Builder(
              builder: (context) {
                inside = context;
                return const ColoredBox(
                  color: Colors.red,
                  child: SizedBox(width: 400, height: 800),
                );
              },
            ),
          ),
        ),
      );

      final image = await tester.runAsync(
        () => LpgGlassSnapshot.capture(inside),
      );

      expect(image, isNotNull);
      expect(image!.width, lessThan(400));
      image.dispose();
    });

    testWidgets('is null when there is no source to take it from', (
      tester,
    ) async {
      late BuildContext inside;
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) {
              inside = context;
              return const SizedBox();
            },
          ),
        ),
      );

      expect(await LpgGlassSnapshot.capture(inside), isNull);
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
      testWidgets('is frosted, with no live blur, in ${v.name}', (
        tester,
      ) async {
        await open(tester, v);

        expect(find.byType(BackdropFilter), findsNothing);
        expect(_paperIn(LpgGlass), findsNWidgets(2));
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
