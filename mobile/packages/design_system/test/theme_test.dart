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
  });
}
