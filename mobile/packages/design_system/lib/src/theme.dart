import 'package:flutter/material.dart';

import 'tokens.dart';

/// Theme variants, mirroring the web themes exactly.
///
/// High contrast is not optional decoration: WCAG 2.2 AA is a Phase 1
/// requirement (D-35), and the mobile apps are held to the same standard as
/// the dashboard.
enum LpgThemeVariant { light, dark, highContrast }

/// Semantic colours exposed to widgets through the theme.
///
/// A `ThemeExtension` rather than raw constants, so widgets read
/// `Theme.of(context).extension<LpgColors>()` and automatically follow the
/// active theme instead of hardcoding a variant's value.
@immutable
class LpgColors extends ThemeExtension<LpgColors> {
  const LpgColors({
    required this.textPrimary,
    required this.textSecondary,
    required this.surfaceBase,
    required this.surfaceRaised,
    required this.borderDefault,
    required this.actionPrimary,
    required this.statusSuccess,
    required this.statusWarning,
    required this.statusDanger,
  });

  final Color textPrimary;
  final Color textSecondary;
  final Color surfaceBase;
  final Color surfaceRaised;
  final Color borderDefault;
  final Color actionPrimary;
  final Color statusSuccess;
  final Color statusWarning;
  final Color statusDanger;

  @override
  LpgColors copyWith({
    Color? textPrimary,
    Color? textSecondary,
    Color? surfaceBase,
    Color? surfaceRaised,
    Color? borderDefault,
    Color? actionPrimary,
    Color? statusSuccess,
    Color? statusWarning,
    Color? statusDanger,
  }) {
    return LpgColors(
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      surfaceBase: surfaceBase ?? this.surfaceBase,
      surfaceRaised: surfaceRaised ?? this.surfaceRaised,
      borderDefault: borderDefault ?? this.borderDefault,
      actionPrimary: actionPrimary ?? this.actionPrimary,
      statusSuccess: statusSuccess ?? this.statusSuccess,
      statusWarning: statusWarning ?? this.statusWarning,
      statusDanger: statusDanger ?? this.statusDanger,
    );
  }

  @override
  LpgColors lerp(ThemeExtension<LpgColors>? other, double t) {
    if (other is! LpgColors) return this;
    return LpgColors(
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      surfaceBase: Color.lerp(surfaceBase, other.surfaceBase, t)!,
      surfaceRaised: Color.lerp(surfaceRaised, other.surfaceRaised, t)!,
      borderDefault: Color.lerp(borderDefault, other.borderDefault, t)!,
      actionPrimary: Color.lerp(actionPrimary, other.actionPrimary, t)!,
      statusSuccess: Color.lerp(statusSuccess, other.statusSuccess, t)!,
      statusWarning: Color.lerp(statusWarning, other.statusWarning, t)!,
      statusDanger: Color.lerp(statusDanger, other.statusDanger, t)!,
    );
  }
}

/// Builds Flutter themes from the generated tokens.
abstract final class LpgTheme {
  static const _light = LpgColors(
    textPrimary: LpgTokensLight.colorTextPrimary,
    textSecondary: LpgTokensLight.colorTextSecondary,
    surfaceBase: LpgTokensLight.colorSurfaceBase,
    surfaceRaised: LpgTokensLight.colorSurfaceRaised,
    borderDefault: LpgTokensLight.colorBorderDefault,
    actionPrimary: LpgTokensLight.colorActionPrimary,
    statusSuccess: LpgTokensLight.colorStatusSuccess,
    statusWarning: LpgTokensLight.colorStatusWarning,
    statusDanger: LpgTokensLight.colorStatusDanger,
  );

  static const _dark = LpgColors(
    textPrimary: LpgTokensDark.colorTextPrimary,
    textSecondary: LpgTokensDark.colorTextSecondary,
    surfaceBase: LpgTokensDark.colorSurfaceBase,
    surfaceRaised: LpgTokensDark.colorSurfaceRaised,
    borderDefault: LpgTokensDark.colorBorderDefault,
    actionPrimary: LpgTokensDark.colorActionPrimary,
    statusSuccess: LpgTokensDark.colorStatusSuccess,
    statusWarning: LpgTokensDark.colorStatusWarning,
    statusDanger: LpgTokensDark.colorStatusDanger,
  );

  static const _highContrast = LpgColors(
    textPrimary: LpgTokensHighContrast.colorTextPrimary,
    textSecondary: LpgTokensHighContrast.colorTextSecondary,
    surfaceBase: LpgTokensHighContrast.colorSurfaceBase,
    surfaceRaised: LpgTokensHighContrast.colorSurfaceRaised,
    borderDefault: LpgTokensHighContrast.colorBorderDefault,
    actionPrimary: LpgTokensHighContrast.colorActionPrimary,
    statusSuccess: LpgTokensHighContrast.colorStatusSuccess,
    statusWarning: LpgTokensHighContrast.colorStatusWarning,
    statusDanger: LpgTokensHighContrast.colorStatusDanger,
  );

  static LpgColors colorsFor(LpgThemeVariant variant) => switch (variant) {
    LpgThemeVariant.light => _light,
    LpgThemeVariant.dark => _dark,
    LpgThemeVariant.highContrast => _highContrast,
  };

  static ThemeData build(LpgThemeVariant variant) {
    final colors = colorsFor(variant);
    final brightness = variant == LpgThemeVariant.dark
        ? Brightness.dark
        : Brightness.light;

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      scaffoldBackgroundColor: colors.surfaceBase,
      colorScheme: ColorScheme.fromSeed(
        seedColor: colors.actionPrimary,
        brightness: brightness,
      ).copyWith(surface: colors.surfaceBase, error: colors.statusDanger),
      extensions: [colors],
    );
  }

  static ThemeData get light => build(LpgThemeVariant.light);
  static ThemeData get dark => build(LpgThemeVariant.dark);
  static ThemeData get highContrast => build(LpgThemeVariant.highContrast);
}
