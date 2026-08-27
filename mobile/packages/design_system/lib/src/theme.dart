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
    required this.textInverse,
    required this.surfaceBase,
    required this.surfaceRaised,
    required this.surfaceOverlay,
    required this.borderDefault,
    required this.borderStrong,
    required this.actionPrimary,
    required this.statusSuccess,
    required this.statusWarning,
    required this.statusDanger,
    required this.statusInfo,
    required this.shadowLight,
    required this.shadowDark,
  });

  final Color textPrimary;
  final Color textSecondary;
  final Color textInverse;
  final Color surfaceBase;
  final Color surfaceRaised;
  final Color surfaceOverlay;
  final Color borderDefault;
  final Color borderStrong;
  final Color actionPrimary;
  final Color statusSuccess;
  final Color statusWarning;
  final Color statusDanger;
  final Color statusInfo;
  final Color shadowLight;
  final Color shadowDark;

  /// Neumorphic "extruded" shadows (convex)
  List<BoxShadow> get neumorphicShadows => [
    BoxShadow(color: shadowLight, offset: const Offset(-4, -4), blurRadius: 10),
    BoxShadow(color: shadowDark, offset: const Offset(4, 4), blurRadius: 10),
  ];

  @override
  LpgColors copyWith({
    Color? textPrimary,
    Color? textSecondary,
    Color? textInverse,
    Color? surfaceBase,
    Color? surfaceRaised,
    Color? surfaceOverlay,
    Color? borderDefault,
    Color? borderStrong,
    Color? actionPrimary,
    Color? statusSuccess,
    Color? statusWarning,
    Color? statusDanger,
    Color? statusInfo,
    Color? shadowLight,
    Color? shadowDark,
  }) {
    return LpgColors(
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      textInverse: textInverse ?? this.textInverse,
      surfaceBase: surfaceBase ?? this.surfaceBase,
      surfaceRaised: surfaceRaised ?? this.surfaceRaised,
      surfaceOverlay: surfaceOverlay ?? this.surfaceOverlay,
      borderDefault: borderDefault ?? this.borderDefault,
      borderStrong: borderStrong ?? this.borderStrong,
      actionPrimary: actionPrimary ?? this.actionPrimary,
      statusSuccess: statusSuccess ?? this.statusSuccess,
      statusWarning: statusWarning ?? this.statusWarning,
      statusDanger: statusDanger ?? this.statusDanger,
      statusInfo: statusInfo ?? this.statusInfo,
      shadowLight: shadowLight ?? this.shadowLight,
      shadowDark: shadowDark ?? this.shadowDark,
    );
  }

  @override
  LpgColors lerp(ThemeExtension<LpgColors>? other, double t) {
    if (other is! LpgColors) return this;
    return LpgColors(
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      textInverse: Color.lerp(textInverse, other.textInverse, t)!,
      surfaceBase: Color.lerp(surfaceBase, other.surfaceBase, t)!,
      surfaceRaised: Color.lerp(surfaceRaised, other.surfaceRaised, t)!,
      surfaceOverlay: Color.lerp(surfaceOverlay, other.surfaceOverlay, t)!,
      borderDefault: Color.lerp(borderDefault, other.borderDefault, t)!,
      borderStrong: Color.lerp(borderStrong, other.borderStrong, t)!,
      actionPrimary: Color.lerp(actionPrimary, other.actionPrimary, t)!,
      statusSuccess: Color.lerp(statusSuccess, other.statusSuccess, t)!,
      statusWarning: Color.lerp(statusWarning, other.statusWarning, t)!,
      statusDanger: Color.lerp(statusDanger, other.statusDanger, t)!,
      statusInfo: Color.lerp(statusInfo, other.statusInfo, t)!,
      shadowLight: Color.lerp(shadowLight, other.shadowLight, t)!,
      shadowDark: Color.lerp(shadowDark, other.shadowDark, t)!,
    );
  }
}

/// Builds Flutter themes from the generated tokens.
abstract final class LpgTheme {
  static const _light = LpgColors(
    textPrimary: LpgTokensLight.colorTextPrimary,
    textSecondary: LpgTokensLight.colorTextSecondary,
    textInverse: LpgTokensLight.colorTextInverse,
    surfaceBase: LpgTokensLight.colorSurfaceBase,
    surfaceRaised: LpgTokensLight.colorSurfaceRaised,
    surfaceOverlay: LpgTokensLight.colorSurfaceOverlay,
    borderDefault: LpgTokensLight.colorBorderDefault,
    borderStrong: LpgTokensLight.colorBorderStrong,
    actionPrimary: LpgTokensLight.colorActionPrimary,
    statusSuccess: LpgTokensLight.colorStatusSuccess,
    statusWarning: LpgTokensLight.colorStatusWarning,
    statusDanger: LpgTokensLight.colorStatusDanger,
    statusInfo: LpgTokensLight.colorStatusInfo,
    shadowLight: Color(0xFFFFFFFF), // pure white for light highlight
    shadowDark: Color(0xFFD1D9E6), // soft grey-blue for light shadow
  );

  static const _dark = LpgColors(
    textPrimary: LpgTokensDark.colorTextPrimary,
    textSecondary: LpgTokensDark.colorTextSecondary,
    textInverse: LpgTokensDark.colorTextInverse,
    surfaceBase: LpgTokensDark.colorSurfaceBase,
    surfaceRaised: LpgTokensDark.colorSurfaceRaised,
    surfaceOverlay: LpgTokensDark.colorSurfaceOverlay,
    borderDefault: LpgTokensDark.colorBorderDefault,
    borderStrong: LpgTokensDark.colorBorderStrong,
    actionPrimary: LpgTokensDark.colorActionPrimary,
    statusSuccess: LpgTokensDark.colorStatusSuccess,
    statusWarning: LpgTokensDark.colorStatusWarning,
    statusDanger: LpgTokensDark.colorStatusDanger,
    statusInfo: LpgTokensDark.colorStatusInfo,
    shadowLight: Color(0xFF1B1F27), // slightly lighter than surfaceBase
    shadowDark: Color(0xFF040609), // slightly darker than surfaceBase
  );

  static const _highContrast = LpgColors(
    textPrimary: LpgTokensHighContrast.colorTextPrimary,
    textSecondary: LpgTokensHighContrast.colorTextSecondary,
    textInverse: LpgTokensHighContrast.colorTextInverse,
    surfaceBase: LpgTokensHighContrast.colorSurfaceBase,
    surfaceRaised: LpgTokensHighContrast.colorSurfaceRaised,
    surfaceOverlay: LpgTokensHighContrast.colorSurfaceOverlay,
    borderDefault: LpgTokensHighContrast.colorBorderDefault,
    borderStrong: LpgTokensHighContrast.colorBorderStrong,
    actionPrimary: LpgTokensHighContrast.colorActionPrimary,
    statusSuccess: LpgTokensHighContrast.colorStatusSuccess,
    statusWarning: LpgTokensHighContrast.colorStatusWarning,
    statusDanger: LpgTokensHighContrast.colorStatusDanger,
    statusInfo: LpgTokensHighContrast.colorStatusInfo,
    shadowLight: Colors.transparent,
    shadowDark: Colors.transparent,
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
      fontFamily: 'Inter', // clean sans-serif typography
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: colors.actionPrimary,
          foregroundColor: LpgTokens.primitiveColorWhite,
          shape: const StadiumBorder(), // Pill-shaped buttons
          padding: const EdgeInsets.symmetric(
            horizontal: LpgTokens.spacingLg * 1.0,
            vertical: LpgTokens.spacingMd * 1.0,
          ),
          elevation: 0,
          textStyle: const TextStyle(
            fontSize: LpgTokens.typographyBodyFontSize * 1.0,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
      ),
      cardTheme: CardThemeData(
        color: colors.surfaceRaised,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LpgTokens.radiusLg * 1.0),
          side: BorderSide(color: colors.borderDefault),
        ),
        margin: EdgeInsets.zero,
      ),
      extensions: [colors],
    );
  }

  static ThemeData get light => build(LpgThemeVariant.light);
  static ThemeData get dark => build(LpgThemeVariant.dark);
  static ThemeData get highContrast => build(LpgThemeVariant.highContrast);
}
