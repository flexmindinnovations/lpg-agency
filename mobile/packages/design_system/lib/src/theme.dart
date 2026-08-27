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
    required this.isHighContrast,
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

  /// Explicit variant flag — components branch on this instead of
  /// back-computing "is this high contrast?" from some other field's
  /// value, which was the previous (fragile) approach here.
  final bool isHighContrast;

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
    bool? isHighContrast,
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
      isHighContrast: isHighContrast ?? this.isHighContrast,
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
      // Not a continuous value — jump partway through the transition
      // rather than pretending a boolean can be interpolated.
      isHighContrast: t < 0.5 ? isHighContrast : other.isHighContrast,
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
    isHighContrast: false,
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
    isHighContrast: false,
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
    isHighContrast: true,
  );

  static LpgColors colorsFor(LpgThemeVariant variant) => switch (variant) {
    LpgThemeVariant.light => _light,
    LpgThemeVariant.dark => _dark,
    LpgThemeVariant.highContrast => _highContrast,
  };

  /// The full M3 role set, built from `LpgTokens.typography*` — every size/
  /// weight/line-height here traces back to a real generated token instead
  /// of Flutter's default Roboto-metric `TextTheme`, which is what actually
  /// rendered before (the typography tokens existed but nothing wired them
  /// into `ThemeData.textTheme`, so components reading e.g.
  /// `theme.textTheme.bodyMedium` were silently getting Material's
  /// defaults). `letterSpacing` on the two largest roles is the one
  /// Flutter-only addition — a deliberate slight tightening on big type,
  /// not a value backed by a token, called out here so it reads as a
  /// choice rather than an oversight.
  /// `LpgTokens.typography*FontWeight` values are plain ints (100-900,
  /// mirroring CSS `font-weight`, since that's the shared source with the
  /// web app) — `FontWeight.values` is the same 100-900 scale in the same
  /// order, so `value ~/ 100 - 1` is the index (700 -> values[6] -> w700).
  static FontWeight _weight(int value) => FontWeight.values[value ~/ 100 - 1];

  static TextTheme _textTheme(LpgColors colors) => TextTheme(
    displayMedium: TextStyle(
      fontSize: LpgTokens.typographyDisplayFontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyDisplayFontWeight),
      height: LpgTokens.typographyDisplayLineHeight.toDouble(),
      letterSpacing: -0.5,
      color: colors.textPrimary,
    ),
    headlineSmall: TextStyle(
      fontSize: LpgTokens.typographyHeading1FontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyHeading1FontWeight),
      height: LpgTokens.typographyHeading1LineHeight.toDouble(),
      letterSpacing: -0.25,
      color: colors.textPrimary,
    ),
    titleMedium: TextStyle(
      fontSize: LpgTokens.typographyHeading2FontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyHeading2FontWeight),
      height: LpgTokens.typographyHeading2LineHeight.toDouble(),
      color: colors.textPrimary,
    ),
    titleSmall: TextStyle(
      fontSize: LpgTokens.typographyHeading3FontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyHeading3FontWeight),
      height: LpgTokens.typographyHeading3LineHeight.toDouble(),
      color: colors.textPrimary,
    ),
    bodyLarge: TextStyle(
      fontSize: LpgTokens.typographyBodyFontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyBodyFontWeight),
      height: LpgTokens.typographyBodyLineHeight.toDouble(),
      color: colors.textPrimary,
    ),
    bodyMedium: TextStyle(
      fontSize: LpgTokens.typographyBodyFontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyBodyFontWeight),
      height: LpgTokens.typographyBodyLineHeight.toDouble(),
      color: colors.textPrimary,
    ),
    bodySmall: TextStyle(
      fontSize: LpgTokens.typographyBodySmallFontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyBodySmallFontWeight),
      height: LpgTokens.typographyBodySmallLineHeight.toDouble(),
      color: colors.textSecondary,
    ),
    labelLarge: TextStyle(
      fontSize: LpgTokens.typographyLabelFontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyLabelFontWeight),
      height: LpgTokens.typographyLabelLineHeight.toDouble(),
      color: colors.textPrimary,
    ),
    labelMedium: TextStyle(
      fontSize: LpgTokens.typographyLabelFontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyLabelFontWeight),
      height: LpgTokens.typographyLabelLineHeight.toDouble(),
      color: colors.textSecondary,
    ),
    labelSmall: TextStyle(
      fontSize: LpgTokens.typographyCaptionFontSize.toDouble(),
      fontWeight: _weight(LpgTokens.typographyCaptionFontWeight),
      height: LpgTokens.typographyCaptionLineHeight.toDouble(),
      color: colors.textSecondary,
    ),
  );

  static ThemeData build(LpgThemeVariant variant) {
    final colors = colorsFor(variant);
    final brightness = variant == LpgThemeVariant.dark
        ? Brightness.dark
        : Brightness.light;
    final textTheme = _textTheme(colors);

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      scaffoldBackgroundColor: colors.surfaceBase,
      colorScheme: ColorScheme.fromSeed(
        seedColor: colors.actionPrimary,
        brightness: brightness,
      ).copyWith(surface: colors.surfaceBase, error: colors.statusDanger),
      fontFamily: 'Inter', // clean sans-serif typography
      textTheme: textTheme,
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
          textStyle: textTheme.labelLarge?.copyWith(
            color: LpgTokens.primitiveColorWhite,
            letterSpacing: 0.5,
          ),
        ),
      ),
      cardTheme: CardThemeData(
        color: colors.surfaceRaised,
        elevation: 0,
        // A "squircle" (continuous corners), not a plain rounded rect —
        // shape carrying visual identity is one of Material 3 Expressive's
        // stated pillars, and `ContinuousRectangleBorder` is Flutter's
        // built-in superellipse curve for exactly this, no custom path
        // drawing required.
        shape: ContinuousRectangleBorder(
          borderRadius: BorderRadius.circular(LpgTokens.radiusLg * 1.5),
          side: colors.isHighContrast
              ? BorderSide(color: colors.borderStrong, width: 2)
              : BorderSide.none,
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
