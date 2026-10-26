import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('LpgTheme', () {
    test('builds all three theme variants', () {
      for (final variant in LpgThemeVariant.values) {
        expect(LpgTheme.build(variant), isA<ThemeData>());
      }
    });

    test('exposes LpgColors as a theme extension', () {
      final theme = LpgTheme.light;
      expect(theme.extension<LpgColors>(), isNotNull);
    });

    test('each variant has distinct surface colours', () {
      // If light and dark resolved to the same value the token pipeline would
      // be silently collapsing themes.
      final light = LpgTheme.colorsFor(LpgThemeVariant.light);
      final dark = LpgTheme.colorsFor(LpgThemeVariant.dark);
      expect(light.surfaceBase, isNot(equals(dark.surfaceBase)));
      expect(light.textPrimary, isNot(equals(dark.textPrimary)));
    });

    test('dark surface is not pure black', () {
      // docs/ui/10-color-system.md section 3: pure black causes halation
      // around light text and increases eye strain.
      final dark = LpgTheme.colorsFor(LpgThemeVariant.dark);
      expect(dark.surfaceBase, isNot(equals(const Color(0xFF000000))));
    });

    test('uses the bundled Inter typeface', () {
      final theme = LpgTheme.light;
      expect(theme.textTheme.bodyLarge?.fontFamily, LpgTheme.fontFamily);
    });

    test('high contrast drops shadows and gradients', () {
      final hc = LpgTheme.colorsFor(LpgThemeVariant.highContrast);
      expect(hc.cardShadow, isEmpty);
      expect(hc.floatingShadow, isEmpty);
      expect(hc.heroGradient.toSet(), hasLength(1));
    });

    test('LpgColors.lerp interpolates between variants', () {
      final light = LpgTheme.colorsFor(LpgThemeVariant.light);
      final dark = LpgTheme.colorsFor(LpgThemeVariant.dark);
      expect(light.lerp(dark, 0).canvas, light.canvas);
      expect(light.lerp(dark, 1).canvas, dark.canvas);
      expect(light.lerp(dark, 1).heroGradient, dark.heroGradient);
    });
  });

  group('LpgFormat', () {
    test('formats rupees with Indian digit grouping', () {
      expect(LpgFormat.currency(124000.5), '₹1,24,000.50');
      expect(LpgFormat.currencyWhole(1240), '₹1,240');
    });

    test('turns status codes into labels and sentences', () {
      expect(LpgFormat.statusLabel('out_for_delivery'), 'Out for delivery');
      expect(LpgFormat.sentence('out_for_delivery'), 'Out for delivery');
      expect(LpgFormat.sentence(''), '');
    });

    test('relative time reads naturally', () {
      final now = DateTime(2026, 10, 17, 12);
      expect(LpgFormat.relative(now, now: now), 'just now');
      expect(
        LpgFormat.relative(now.subtract(const Duration(minutes: 5)), now: now),
        '5 min ago',
      );
      expect(
        LpgFormat.relative(now.subtract(const Duration(hours: 3)), now: now),
        '3 h ago',
      );
      expect(
        LpgFormat.relative(now.subtract(const Duration(days: 1)), now: now),
        'yesterday',
      );
    });
  });
}
