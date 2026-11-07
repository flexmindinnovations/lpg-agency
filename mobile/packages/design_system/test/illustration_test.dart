import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/gallery_harness.dart';

double _contrast(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  final hi = la > lb ? la : lb;
  final lo = la > lb ? lb : la;
  return (hi + 0.05) / (lo + 0.05);
}

void main() {
  group('illustration contrast (WCAG 2.2 AA)', () {
    // Text can end up over any layer of a picture, so the strongest tint of
    // every tone must still give the tile's text 4.5:1. A tile with a picture
    // uses the primary text colour for that reason: the secondary colour only
    // just clears 4.5:1 on a plain card.
    for (final variant in LpgThemeVariant.values) {
      for (final tone in LpgTone.values) {
        test('${variant.name} / ${tone.name}: text clears 4.5:1', () {
          final colors = LpgTheme.colorsFor(variant);
          if (colors.isHighContrast) return; // no picture is drawn there
          final strongest = colors.tint(
            tone.foreground(colors),
            LpgIllustrationTint.strong,
          );
          final primary = _contrast(colors.textPrimary, strongest);
          expect(primary, greaterThanOrEqualTo(4.5));
        });
      }
    }
  });

  group('LpgMetricTile with an illustration', () {
    Widget host(Widget child, {bool reduceMotion = false, ThemeData? theme}) =>
        MaterialApp(
          theme: theme ?? LpgTheme.light,
          home: MediaQuery(
            data: MediaQueryData(disableAnimations: reduceMotion),
            child: Scaffold(
              body: Center(child: SizedBox(width: 180, child: child)),
            ),
          ),
        );

    LpgMetricTile tile({LpgIllustration? art, VoidCallback? onTap}) =>
        LpgMetricTile(
          label: 'Short',
          value: '₹5,500',
          caption: '2 handovers',
          icon: Icons.warning,
          tone: LpgTone.danger,
          illustration: art,
          onTap: onTap,
        );

    testWidgets('changes neither the size nor the semantics of the tile', (
      tester,
    ) async {
      await tester.pumpWidget(host(tile(), reduceMotion: true));
      final plainSize = tester.getSize(find.byType(LpgMetricTile));
      final plainValue = tester.getTopLeft(find.text('₹5,500'));

      await tester.pumpWidget(
        host(tile(art: LpgIllustration.shortfall), reduceMotion: true),
      );

      expect(tester.getSize(find.byType(LpgMetricTile)), plainSize);
      expect(tester.getTopLeft(find.text('₹5,500')), plainValue);
      expect(
        find.bySemanticsLabel('Short: ₹5,500, 2 handovers'),
        findsOneWidget,
      );
    });

    testWidgets('the picture does not take the tap', (tester) async {
      var taps = 0;
      await tester.pumpWidget(
        host(
          tile(art: LpgIllustration.excess, onTap: () => taps++),
          reduceMotion: true,
        ),
      );
      // The bottom-right corner is where the picture is drawn.
      final corner = tester.getBottomRight(find.byType(LpgMetricTile));
      await tester.tapAt(corner - const Offset(8, 8));
      expect(taps, 1);
    });

    testWidgets('label and caption use the primary text colour', (
      tester,
    ) async {
      Color? labelColor() =>
          tester.widget<Text>(find.text('Short')).style?.color;
      final colors = LpgTheme.colorsFor(LpgThemeVariant.light);

      await tester.pumpWidget(host(tile(), reduceMotion: true));
      expect(labelColor(), colors.textSecondary);

      await tester.pumpWidget(
        host(tile(art: LpgIllustration.shortfall), reduceMotion: true),
      );
      expect(labelColor(), colors.textPrimary);
    });

    for (final reduce in [false, true]) {
      testWidgets('is still: nothing animates (reduce-motion: $reduce)', (
        tester,
      ) async {
        await tester.pumpWidget(
          host(tile(art: LpgIllustration.banknotes), reduceMotion: reduce),
        );
        await settleAssets(tester);

        expect(tester.hasRunningAnimations, isFalse);
        expect(
          find.descendant(
            of: find.byType(LpgIllustrationArt),
            matching: find.byType(SvgPicture),
          ),
          findsOneWidget,
        );
      });
    }

    testWidgets('in high contrast no picture is drawn', (tester) async {
      await tester.pumpWidget(
        host(
          tile(art: LpgIllustration.shortfall),
          reduceMotion: true,
          theme: LpgTheme.highContrast,
        ),
      );
      expect(
        find.descendant(
          of: find.byType(LpgIllustrationArt),
          matching: find.byType(SvgPicture),
        ),
        findsNothing,
      );
    });
  });
}
