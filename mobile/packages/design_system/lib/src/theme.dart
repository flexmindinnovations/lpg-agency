import 'package:flutter/cupertino.dart' show CupertinoPageTransitionsBuilder;
import 'package:flutter/material.dart';

import 'layout.dart';
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
/// `Theme.of(context).extension<LpgColors>()` (or the shorter
/// `context.lpgColors`) and automatically follow the active theme instead of
/// hardcoding a variant's value.
///
/// Every colour here traces back to `design-tokens/tokens.json`. To rebrand
/// the apps, change the `gasBlue` (primary) and `flameOrange` (accent)
/// primitives there and run `node scripts/generate-tokens.mjs`; nothing in
/// this file or in any screen needs to change.
@immutable
class LpgColors extends ThemeExtension<LpgColors> {
  const LpgColors({
    required this.textPrimary,
    required this.textSecondary,
    required this.textDisabled,
    required this.textInverse,
    required this.surfaceBase,
    required this.surfaceRaised,
    required this.surfaceOverlay,
    required this.canvas,
    required this.card,
    required this.borderDefault,
    required this.borderStrong,
    required this.borderFocus,
    required this.actionPrimary,
    required this.actionPrimaryContainer,
    required this.onActionPrimaryContainer,
    required this.accent,
    required this.statusSuccess,
    required this.statusWarning,
    required this.statusDanger,
    required this.statusInfo,
    required this.heroGradient,
    required this.onHero,
    required this.cardShadow,
    required this.floatingShadow,
    required this.isHighContrast,
  });

  final Color textPrimary;
  final Color textSecondary;
  final Color textDisabled;
  final Color textInverse;
  final Color surfaceBase;
  final Color surfaceRaised;
  final Color surfaceOverlay;

  /// The page background behind cards. Light mode sits cards on a faintly
  /// tinted canvas so white cards read as raised; dark mode does the
  /// opposite (darkest canvas, lighter cards), since elevation in dark
  /// themes is communicated by lightness, not shadow.
  final Color canvas;

  /// The fill of cards, list groups and other raised containers.
  final Color card;
  final Color borderDefault;
  final Color borderStrong;
  final Color borderFocus;
  final Color actionPrimary;

  /// A quiet tint of the primary colour, for selected chips, the active
  /// navigation indicator and tonal buttons.
  final Color actionPrimaryContainer;
  final Color onActionPrimaryContainer;

  /// The brand's secondary, high-energy colour: highlights and the brand
  /// mark, never status (status colours stay independent of brand).
  final Color accent;
  final Color statusSuccess;
  final Color statusWarning;
  final Color statusDanger;
  final Color statusInfo;

  /// The brand gradient behind hero panels (the dashboard balance card, the
  /// sign-in header). Two stops, start to end.
  final List<Color> heroGradient;

  /// Text and icons drawn on [heroGradient].
  final Color onHero;

  /// Resting elevation for cards (mirrors the `elevation.1` token).
  final List<BoxShadow> cardShadow;

  /// Floating elevation for sheets, the navigation bar and pressed-up
  /// surfaces (mirrors the `elevation.3` token).
  final List<BoxShadow> floatingShadow;

  /// Explicit variant flag — components branch on this instead of
  /// back-computing "is this high contrast?" from some other field's
  /// value, which was the previous (fragile) approach here.
  final bool isHighContrast;

  @override
  LpgColors copyWith({
    Color? textPrimary,
    Color? textSecondary,
    Color? textDisabled,
    Color? textInverse,
    Color? surfaceBase,
    Color? surfaceRaised,
    Color? surfaceOverlay,
    Color? canvas,
    Color? card,
    Color? borderDefault,
    Color? borderStrong,
    Color? borderFocus,
    Color? actionPrimary,
    Color? actionPrimaryContainer,
    Color? onActionPrimaryContainer,
    Color? accent,
    Color? statusSuccess,
    Color? statusWarning,
    Color? statusDanger,
    Color? statusInfo,
    List<Color>? heroGradient,
    Color? onHero,
    List<BoxShadow>? cardShadow,
    List<BoxShadow>? floatingShadow,
    bool? isHighContrast,
  }) {
    return LpgColors(
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      textDisabled: textDisabled ?? this.textDisabled,
      textInverse: textInverse ?? this.textInverse,
      surfaceBase: surfaceBase ?? this.surfaceBase,
      surfaceRaised: surfaceRaised ?? this.surfaceRaised,
      surfaceOverlay: surfaceOverlay ?? this.surfaceOverlay,
      canvas: canvas ?? this.canvas,
      card: card ?? this.card,
      borderDefault: borderDefault ?? this.borderDefault,
      borderStrong: borderStrong ?? this.borderStrong,
      borderFocus: borderFocus ?? this.borderFocus,
      actionPrimary: actionPrimary ?? this.actionPrimary,
      actionPrimaryContainer:
          actionPrimaryContainer ?? this.actionPrimaryContainer,
      onActionPrimaryContainer:
          onActionPrimaryContainer ?? this.onActionPrimaryContainer,
      accent: accent ?? this.accent,
      statusSuccess: statusSuccess ?? this.statusSuccess,
      statusWarning: statusWarning ?? this.statusWarning,
      statusDanger: statusDanger ?? this.statusDanger,
      statusInfo: statusInfo ?? this.statusInfo,
      heroGradient: heroGradient ?? this.heroGradient,
      onHero: onHero ?? this.onHero,
      cardShadow: cardShadow ?? this.cardShadow,
      floatingShadow: floatingShadow ?? this.floatingShadow,
      isHighContrast: isHighContrast ?? this.isHighContrast,
    );
  }

  @override
  LpgColors lerp(ThemeExtension<LpgColors>? other, double t) {
    if (other is! LpgColors) return this;
    Color c(Color a, Color b) => Color.lerp(a, b, t)!;
    return LpgColors(
      textPrimary: c(textPrimary, other.textPrimary),
      textSecondary: c(textSecondary, other.textSecondary),
      textDisabled: c(textDisabled, other.textDisabled),
      textInverse: c(textInverse, other.textInverse),
      surfaceBase: c(surfaceBase, other.surfaceBase),
      surfaceRaised: c(surfaceRaised, other.surfaceRaised),
      surfaceOverlay: c(surfaceOverlay, other.surfaceOverlay),
      canvas: c(canvas, other.canvas),
      card: c(card, other.card),
      borderDefault: c(borderDefault, other.borderDefault),
      borderStrong: c(borderStrong, other.borderStrong),
      borderFocus: c(borderFocus, other.borderFocus),
      actionPrimary: c(actionPrimary, other.actionPrimary),
      actionPrimaryContainer: c(
        actionPrimaryContainer,
        other.actionPrimaryContainer,
      ),
      onActionPrimaryContainer: c(
        onActionPrimaryContainer,
        other.onActionPrimaryContainer,
      ),
      accent: c(accent, other.accent),
      statusSuccess: c(statusSuccess, other.statusSuccess),
      statusWarning: c(statusWarning, other.statusWarning),
      statusDanger: c(statusDanger, other.statusDanger),
      statusInfo: c(statusInfo, other.statusInfo),
      heroGradient: [
        for (var i = 0; i < heroGradient.length; i++)
          c(heroGradient[i], other.heroGradient[i]),
      ],
      onHero: c(onHero, other.onHero),
      cardShadow: BoxShadow.lerpList(cardShadow, other.cardShadow, t)!,
      floatingShadow: BoxShadow.lerpList(
        floatingShadow,
        other.floatingShadow,
        t,
      )!,
      // Not a continuous value — jump partway through the transition
      // rather than pretending a boolean can be interpolated.
      isHighContrast: t < 0.5 ? isHighContrast : other.isHighContrast,
    );
  }
}

/// Shorthand for the two lookups every widget makes.
extension LpgThemeContext on BuildContext {
  LpgColors get lpgColors => Theme.of(this).extension<LpgColors>()!;
  TextTheme get lpgText => Theme.of(this).textTheme;
}

/// Builds Flutter themes from the generated tokens.
abstract final class LpgTheme {
  /// The bundled typeface (see the design_system pubspec). The `packages/`
  /// prefix is how Flutter addresses a font declared by a dependency.
  static const fontFamily = 'packages/design_system/Inter';

  // Shadows mirror the `elevation.*` tokens in design-tokens/tokens.json.
  // Those are CSS box-shadow strings the generator can't express as Dart, so
  // the same offsets/blur/alpha are restated here, once.
  static const _black = LpgTokens.primitiveColorBlack;

  static final _lightCardShadow = [
    BoxShadow(
      color: _black.withValues(alpha: 0.06),
      offset: const Offset(0, 1),
      blurRadius: 2,
    ),
    BoxShadow(
      color: _black.withValues(alpha: 0.08),
      offset: const Offset(0, 1),
      blurRadius: 3,
    ),
  ];

  static final _lightFloatingShadow = [
    BoxShadow(
      color: _black.withValues(alpha: 0.12),
      offset: const Offset(0, 12),
      blurRadius: 24,
    ),
    BoxShadow(
      color: _black.withValues(alpha: 0.08),
      offset: const Offset(0, 4),
      blurRadius: 8,
    ),
  ];

  static final _darkCardShadow = [
    BoxShadow(
      color: _black.withValues(alpha: 0.40),
      offset: const Offset(0, 1),
      blurRadius: 2,
    ),
  ];

  static final _darkFloatingShadow = [
    BoxShadow(
      color: _black.withValues(alpha: 0.60),
      offset: const Offset(0, 12),
      blurRadius: 24,
    ),
  ];

  static final _light = LpgColors(
    textPrimary: LpgTokensLight.colorTextPrimary,
    textSecondary: LpgTokensLight.colorTextSecondary,
    textDisabled: LpgTokensLight.colorTextDisabled,
    textInverse: LpgTokensLight.colorTextInverse,
    surfaceBase: LpgTokensLight.colorSurfaceBase,
    surfaceRaised: LpgTokensLight.colorSurfaceRaised,
    surfaceOverlay: LpgTokensLight.colorSurfaceOverlay,
    canvas: LpgTokensLight.colorSurfaceRaised,
    card: LpgTokensLight.colorSurfaceBase,
    borderDefault: LpgTokensLight.colorBorderDefault,
    borderStrong: LpgTokensLight.colorBorderStrong,
    borderFocus: LpgTokensLight.colorBorderFocus,
    actionPrimary: LpgTokensLight.colorActionPrimary,
    actionPrimaryContainer: LpgTokens.primitiveColorGasBlue50,
    onActionPrimaryContainer: LpgTokens.primitiveColorGasBlue800,
    accent: LpgTokens.primitiveColorFlameOrange500,
    statusSuccess: LpgTokensLight.colorStatusSuccess,
    statusWarning: LpgTokensLight.colorStatusWarning,
    statusDanger: LpgTokensLight.colorStatusDanger,
    statusInfo: LpgTokensLight.colorStatusInfo,
    heroGradient: const [
      LpgTokens.primitiveColorGasBlue800,
      LpgTokens.primitiveColorGasBlue500,
    ],
    onHero: LpgTokens.primitiveColorWhite,
    cardShadow: _lightCardShadow,
    floatingShadow: _lightFloatingShadow,
    isHighContrast: false,
  );

  static final _dark = LpgColors(
    textPrimary: LpgTokensDark.colorTextPrimary,
    textSecondary: LpgTokensDark.colorTextSecondary,
    textDisabled: LpgTokensDark.colorTextDisabled,
    textInverse: LpgTokensDark.colorTextInverse,
    surfaceBase: LpgTokensDark.colorSurfaceBase,
    surfaceRaised: LpgTokensDark.colorSurfaceRaised,
    surfaceOverlay: LpgTokensDark.colorSurfaceOverlay,
    canvas: LpgTokensDark.colorSurfaceBase,
    card: LpgTokensDark.colorSurfaceRaised,
    borderDefault: LpgTokensDark.colorBorderDefault,
    borderStrong: LpgTokensDark.colorBorderStrong,
    borderFocus: LpgTokensDark.colorBorderFocus,
    actionPrimary: LpgTokensDark.colorActionPrimary,
    actionPrimaryContainer: LpgTokens.primitiveColorGasBlue900,
    onActionPrimaryContainer: LpgTokens.primitiveColorGasBlue100,
    accent: LpgTokens.primitiveColorFlameOrange400,
    statusSuccess: LpgTokensDark.colorStatusSuccess,
    statusWarning: LpgTokensDark.colorStatusWarning,
    statusDanger: LpgTokensDark.colorStatusDanger,
    statusInfo: LpgTokensDark.colorStatusInfo,
    heroGradient: const [
      LpgTokens.primitiveColorGasBlue700,
      LpgTokens.primitiveColorGasBlue900,
    ],
    onHero: LpgTokens.primitiveColorWhite,
    cardShadow: _darkCardShadow,
    floatingShadow: _darkFloatingShadow,
    isHighContrast: false,
  );

  // High contrast: no gradients, no shadows (borders carry separation, per
  // docs/ui/10-color-system.md section 4), and accent collapses to the same
  // action blue so nothing relies on a mid-tone orange for meaning.
  static const _highContrast = LpgColors(
    textPrimary: LpgTokensHighContrast.colorTextPrimary,
    textSecondary: LpgTokensHighContrast.colorTextSecondary,
    textDisabled: LpgTokensHighContrast.colorTextDisabled,
    textInverse: LpgTokensHighContrast.colorTextInverse,
    surfaceBase: LpgTokensHighContrast.colorSurfaceBase,
    surfaceRaised: LpgTokensHighContrast.colorSurfaceRaised,
    surfaceOverlay: LpgTokensHighContrast.colorSurfaceOverlay,
    canvas: LpgTokensHighContrast.colorSurfaceBase,
    card: LpgTokensHighContrast.colorSurfaceRaised,
    borderDefault: LpgTokensHighContrast.colorBorderDefault,
    borderStrong: LpgTokensHighContrast.colorBorderStrong,
    borderFocus: LpgTokensHighContrast.colorBorderFocus,
    actionPrimary: LpgTokensHighContrast.colorActionPrimary,
    actionPrimaryContainer: LpgTokens.primitiveColorWhite,
    onActionPrimaryContainer: LpgTokensHighContrast.colorActionPrimary,
    accent: LpgTokensHighContrast.colorActionPrimary,
    statusSuccess: LpgTokensHighContrast.colorStatusSuccess,
    statusWarning: LpgTokensHighContrast.colorStatusWarning,
    statusDanger: LpgTokensHighContrast.colorStatusDanger,
    statusInfo: LpgTokensHighContrast.colorStatusInfo,
    heroGradient: [
      LpgTokensHighContrast.colorActionPrimary,
      LpgTokensHighContrast.colorActionPrimary,
    ],
    onHero: LpgTokens.primitiveColorWhite,
    cardShadow: [],
    floatingShadow: [],
    isHighContrast: true,
  );

  static LpgColors colorsFor(LpgThemeVariant variant) => switch (variant) {
    LpgThemeVariant.light => _light,
    LpgThemeVariant.dark => _dark,
    LpgThemeVariant.highContrast => _highContrast,
  };

  /// `LpgTokens.typography*FontWeight` values are plain ints (100-900,
  /// mirroring CSS `font-weight`, since that's the shared source with the
  /// web app) — `FontWeight.values` is the same 100-900 scale in the same
  /// order, so `value ~/ 100 - 1` is the index (700 -> values[6] -> w700).
  static FontWeight _weight(int value) => FontWeight.values[value ~/ 100 - 1];

  static TextStyle _style({
    required int size,
    required int weight,
    required num height,
    required Color color,
    double letterSpacing = 0,
  }) => TextStyle(
    fontFamily: fontFamily,
    fontSize: size.toDouble(),
    fontWeight: _weight(weight),
    height: height.toDouble(),
    letterSpacing: letterSpacing,
    color: color,
  );

  /// The full M3 role set, built from `LpgTokens.typography*` — every size/
  /// weight/line-height here traces back to a generated token. The
  /// `letterSpacing` values are the one Flutter-only addition: Inter is
  /// designed to be tracked slightly tighter as it gets larger, so display
  /// and headline roles tighten a little and labels open up a little.
  static TextTheme _textTheme(LpgColors colors) => TextTheme(
    displayLarge: _style(
      size: LpgTokens.typographyDisplayFontSize,
      weight: LpgTokens.typographyDisplayFontWeight,
      height: LpgTokens.typographyDisplayLineHeight,
      letterSpacing: -0.8,
      color: colors.textPrimary,
    ),
    displayMedium: _style(
      size: LpgTokens.typographyDisplayFontSize,
      weight: LpgTokens.typographyDisplayFontWeight,
      height: LpgTokens.typographyDisplayLineHeight,
      letterSpacing: -0.5,
      color: colors.textPrimary,
    ),
    displaySmall: _style(
      size: LpgTokens.typographyHeading1FontSize,
      weight: LpgTokens.typographyDisplayFontWeight,
      height: LpgTokens.typographyDisplayLineHeight,
      letterSpacing: -0.5,
      color: colors.textPrimary,
    ),
    headlineLarge: _style(
      size: LpgTokens.typographyDisplayFontSize,
      weight: LpgTokens.typographyHeading1FontWeight,
      height: LpgTokens.typographyHeading1LineHeight,
      letterSpacing: -0.5,
      color: colors.textPrimary,
    ),
    headlineMedium: _style(
      size: LpgTokens.typographyHeading1FontSize,
      weight: LpgTokens.typographyHeading1FontWeight,
      height: LpgTokens.typographyHeading1LineHeight,
      letterSpacing: -0.4,
      color: colors.textPrimary,
    ),
    headlineSmall: _style(
      size: LpgTokens.typographyHeading1FontSize,
      weight: LpgTokens.typographyHeading1FontWeight,
      height: LpgTokens.typographyHeading1LineHeight,
      letterSpacing: -0.25,
      color: colors.textPrimary,
    ),
    titleLarge: _style(
      size: LpgTokens.typographyHeading2FontSize,
      weight: LpgTokens.typographyHeading1FontWeight,
      height: LpgTokens.typographyHeading2LineHeight,
      letterSpacing: -0.2,
      color: colors.textPrimary,
    ),
    titleMedium: _style(
      size: LpgTokens.typographyHeading2FontSize,
      weight: LpgTokens.typographyHeading2FontWeight,
      height: LpgTokens.typographyHeading2LineHeight,
      color: colors.textPrimary,
    ),
    titleSmall: _style(
      size: LpgTokens.typographyHeading3FontSize,
      weight: LpgTokens.typographyHeading3FontWeight,
      height: LpgTokens.typographyHeading3LineHeight,
      color: colors.textPrimary,
    ),
    bodyLarge: _style(
      size: LpgTokens.typographyBodyFontSize,
      weight: LpgTokens.typographyBodyFontWeight,
      height: LpgTokens.typographyBodyLineHeight,
      color: colors.textPrimary,
    ),
    bodyMedium: _style(
      size: LpgTokens.typographyBodySmallFontSize,
      weight: LpgTokens.typographyBodyFontWeight,
      height: LpgTokens.typographyBodyLineHeight,
      color: colors.textPrimary,
    ),
    bodySmall: _style(
      size: LpgTokens.typographyCaptionFontSize,
      weight: LpgTokens.typographyBodySmallFontWeight,
      height: LpgTokens.typographyBodySmallLineHeight,
      color: colors.textSecondary,
    ),
    labelLarge: _style(
      size: LpgTokens.typographyLabelFontSize,
      weight: LpgTokens.typographyHeading3FontWeight,
      height: LpgTokens.typographyLabelLineHeight,
      letterSpacing: 0.1,
      color: colors.textPrimary,
    ),
    labelMedium: _style(
      size: LpgTokens.typographyCaptionFontSize,
      weight: LpgTokens.typographyLabelFontWeight,
      height: LpgTokens.typographyLabelLineHeight,
      letterSpacing: 0.2,
      color: colors.textSecondary,
    ),
    labelSmall: _style(
      size: LpgTokens.typographyCaptionFontSize,
      weight: LpgTokens.typographyCaptionFontWeight,
      height: LpgTokens.typographyCaptionLineHeight,
      letterSpacing: 0.3,
      color: colors.textSecondary,
    ),
  );

  static ThemeData build(LpgThemeVariant variant) {
    final colors = colorsFor(variant);
    final brightness = variant == LpgThemeVariant.dark
        ? Brightness.dark
        : Brightness.light;
    final textTheme = _textTheme(colors);
    final hc = colors.isHighContrast;
    final borderWidth = hc ? 2.0 : 1.0;
    final cardBorder = BorderSide(
      color: hc ? colors.borderStrong : colors.borderDefault,
      width: borderWidth,
    );

    final colorScheme =
        ColorScheme.fromSeed(
          seedColor: colors.actionPrimary,
          brightness: brightness,
        ).copyWith(
          primary: colors.actionPrimary,
          onPrimary: LpgTokensLight.colorActionPrimaryText,
          primaryContainer: colors.actionPrimaryContainer,
          onPrimaryContainer: colors.onActionPrimaryContainer,
          secondary: colors.accent,
          surface: colors.canvas,
          onSurface: colors.textPrimary,
          onSurfaceVariant: colors.textSecondary,
          surfaceContainerLowest: colors.card,
          surfaceContainerLow: colors.card,
          surfaceContainer: colors.card,
          surfaceContainerHigh: colors.surfaceOverlay,
          surfaceContainerHighest: colors.surfaceOverlay,
          outline: colors.borderStrong,
          outlineVariant: colors.borderDefault,
          error: colors.statusDanger,
          surfaceTint: Colors.transparent,
        );

    final inputRadius = BorderRadius.circular(LpgRadius.lg);
    OutlineInputBorder inputBorder(Color color, [double? width]) =>
        OutlineInputBorder(
          borderRadius: inputRadius,
          borderSide: BorderSide(color: color, width: width ?? borderWidth),
        );

    final buttonShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(LpgRadius.lg),
    );
    const buttonPadding = EdgeInsets.symmetric(
      horizontal: LpgSpacing.lg,
      vertical: LpgSpacing.md,
    );
    const buttonMinSize = Size(LpgSizes.touchTarget, LpgSizes.touchTarget);

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: colors.canvas,
      canvasColor: colors.canvas,
      fontFamily: fontFamily,
      textTheme: textTheme,
      dividerColor: colors.borderDefault,
      splashFactory: InkSparkle.splashFactory,
      visualDensity: VisualDensity.standard,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.android: PredictiveBackPageTransitionsBuilder(),
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.linux: FadeForwardsPageTransitionsBuilder(),
          TargetPlatform.windows: FadeForwardsPageTransitionsBuilder(),
        },
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: colors.canvas,
        foregroundColor: colors.textPrimary,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        // A hairline appears once content scrolls underneath, instead of a
        // permanent divider.
        scrolledUnderElevation: hc ? 0 : 0.5,
        shadowColor: colors.borderStrong,
        centerTitle: false,
        titleSpacing: LpgSpacing.mdl,
        titleTextStyle: textTheme.titleLarge,
        iconTheme: IconThemeData(
          color: colors.textPrimary,
          size: LpgSizes.iconLg,
        ),
        actionsIconTheme: IconThemeData(
          color: colors.textPrimary,
          size: LpgSizes.iconLg,
        ),
        shape: hc
            ? Border(bottom: BorderSide(color: colors.borderStrong, width: 2))
            : null,
      ),
      iconTheme: IconThemeData(
        color: colors.textPrimary,
        size: LpgSizes.iconLg,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: colors.card,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        height: LpgSizes.touchTarget + LpgSpacing.lg,
        indicatorColor: hc
            ? colors.actionPrimary
            : colors.actionPrimaryContainer,
        indicatorShape: const StadiumBorder(),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            size: LpgSizes.iconLg,
            color: states.contains(WidgetState.selected)
                ? (hc ? colors.textInverse : colors.onActionPrimaryContainer)
                : colors.textSecondary,
          ),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => textTheme.labelMedium?.copyWith(
            color: states.contains(WidgetState.selected)
                ? colors.textPrimary
                : colors.textSecondary,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w700
                : FontWeight.w500,
          ),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: colors.actionPrimary,
          foregroundColor: LpgTokensLight.colorActionPrimaryText,
          disabledBackgroundColor: colors.surfaceOverlay,
          disabledForegroundColor: colors.textDisabled,
          minimumSize: buttonMinSize,
          padding: buttonPadding,
          shape: buttonShape,
          textStyle: textTheme.labelLarge,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: colors.actionPrimary,
          foregroundColor: LpgTokensLight.colorActionPrimaryText,
          minimumSize: buttonMinSize,
          padding: buttonPadding,
          shape: buttonShape,
          elevation: 0,
          textStyle: textTheme.labelLarge,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: colors.textPrimary,
          minimumSize: buttonMinSize,
          padding: buttonPadding,
          shape: buttonShape,
          side: BorderSide(
            color: hc ? colors.borderStrong : colors.borderDefault,
            width: borderWidth,
          ),
          textStyle: textTheme.labelLarge,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: colors.actionPrimary,
          minimumSize: buttonMinSize,
          shape: buttonShape,
          textStyle: textTheme.labelLarge,
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: colors.textPrimary,
          minimumSize: buttonMinSize,
        ),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: colors.actionPrimary,
        foregroundColor: LpgTokensLight.colorActionPrimaryText,
        elevation: hc ? 0 : 2,
        highlightElevation: hc ? 0 : 4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LpgRadius.xl),
        ),
        extendedTextStyle: textTheme.labelLarge,
      ),
      cardTheme: CardThemeData(
        color: colors.card,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: LpgRadius.cardRadius,
          side: cardBorder,
        ),
        margin: EdgeInsets.zero,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colors.card,
        hintStyle: textTheme.bodyLarge?.copyWith(color: colors.textDisabled),
        labelStyle: textTheme.bodyLarge?.copyWith(color: colors.textSecondary),
        floatingLabelStyle: textTheme.labelLarge?.copyWith(
          color: colors.actionPrimary,
        ),
        helperStyle: textTheme.bodySmall,
        errorStyle: textTheme.bodySmall?.copyWith(color: colors.statusDanger),
        prefixIconColor: colors.textSecondary,
        suffixIconColor: colors.textSecondary,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: LpgSpacing.md,
          vertical: LpgSpacing.md,
        ),
        border: inputBorder(colors.borderDefault),
        enabledBorder: inputBorder(
          hc ? colors.borderStrong : colors.borderDefault,
        ),
        disabledBorder: inputBorder(colors.borderDefault),
        focusedBorder: inputBorder(colors.borderFocus, 2),
        errorBorder: inputBorder(colors.statusDanger),
        focusedErrorBorder: inputBorder(colors.statusDanger, 2),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: colors.card,
        selectedColor: colors.actionPrimaryContainer,
        disabledColor: colors.surfaceOverlay,
        labelStyle: textTheme.labelLarge,
        secondaryLabelStyle: textTheme.labelLarge?.copyWith(
          color: colors.onActionPrimaryContainer,
        ),
        side: cardBorder,
        shape: const StadiumBorder(),
        checkmarkColor: colors.onActionPrimaryContainer,
        padding: const EdgeInsets.symmetric(
          horizontal: LpgSpacing.sm,
          vertical: LpgSpacing.xs,
        ),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? colors.actionPrimaryContainer
                : colors.card,
          ),
          foregroundColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? colors.onActionPrimaryContainer
                : colors.textPrimary,
          ),
          side: WidgetStatePropertyAll(cardBorder),
          textStyle: WidgetStatePropertyAll(textTheme.labelLarge),
        ),
      ),
      listTileTheme: ListTileThemeData(
        iconColor: colors.textSecondary,
        textColor: colors.textPrimary,
        titleTextStyle: textTheme.titleSmall,
        subtitleTextStyle: textTheme.bodySmall,
        contentPadding: const EdgeInsets.symmetric(horizontal: LpgSpacing.md),
        minVerticalPadding: LpgSpacing.smd,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LpgRadius.lg),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: hc ? colors.borderStrong : colors.borderDefault,
        thickness: hc ? 2 : 1,
        space: 1,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: colors.card,
        surfaceTintColor: Colors.transparent,
        elevation: hc ? 0 : 6,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LpgRadius.xxl),
          side: hc ? cardBorder : BorderSide.none,
        ),
        titleTextStyle: textTheme.titleLarge,
        contentTextStyle: textTheme.bodyMedium?.copyWith(
          color: colors.textSecondary,
        ),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: colors.card,
        modalBackgroundColor: colors.card,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        dragHandleColor: colors.borderStrong,
        elevation: hc ? 0 : 8,
        modalElevation: hc ? 0 : 8,
        shape: RoundedRectangleBorder(
          borderRadius: const BorderRadius.vertical(
            top: Radius.circular(LpgRadius.xxl),
          ),
          side: hc ? cardBorder : BorderSide.none,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: hc
            ? colors.textPrimary
            : LpgTokens.primitiveColorGray900,
        contentTextStyle: textTheme.bodyMedium?.copyWith(
          color: LpgTokens.primitiveColorWhite,
        ),
        actionTextColor: hc
            ? colors.textInverse
            : LpgTokens.primitiveColorGasBlue300,
        elevation: hc ? 0 : 4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LpgRadius.lg),
        ),
        insetPadding: const EdgeInsets.all(LpgSpacing.md),
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: colors.actionPrimary,
        linearTrackColor: colors.surfaceOverlay,
        circularTrackColor: Colors.transparent,
        linearMinHeight: LpgSpacing.xs,
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? LpgTokensLight.colorActionPrimaryText
              : colors.borderStrong,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? colors.actionPrimary
              : colors.surfaceOverlay,
        ),
        trackOutlineColor: WidgetStatePropertyAll(colors.borderStrong),
      ),
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? colors.actionPrimary
              : Colors.transparent,
        ),
        side: BorderSide(color: colors.borderStrong, width: 1.5),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LpgRadius.sm),
        ),
      ),
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? colors.actionPrimary
              : colors.borderStrong,
        ),
      ),
      tabBarTheme: TabBarThemeData(
        labelColor: colors.actionPrimary,
        unselectedLabelColor: colors.textSecondary,
        indicatorColor: colors.actionPrimary,
        labelStyle: textTheme.labelLarge,
        unselectedLabelStyle: textTheme.labelLarge,
        dividerColor: colors.borderDefault,
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: LpgTokens.primitiveColorGray900,
          borderRadius: BorderRadius.circular(LpgRadius.md),
        ),
        textStyle: textTheme.labelMedium?.copyWith(
          color: LpgTokens.primitiveColorWhite,
        ),
      ),
      badgeTheme: BadgeThemeData(
        backgroundColor: colors.statusDanger,
        textColor: LpgTokens.primitiveColorWhite,
      ),
      dropdownMenuTheme: DropdownMenuThemeData(
        textStyle: textTheme.bodyLarge,
        menuStyle: MenuStyle(
          backgroundColor: WidgetStatePropertyAll(colors.card),
          surfaceTintColor: const WidgetStatePropertyAll(Colors.transparent),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(LpgRadius.lg),
            ),
          ),
        ),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: colors.card,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LpgRadius.lg),
          side: hc ? cardBorder : BorderSide.none,
        ),
      ),
      datePickerTheme: DatePickerThemeData(
        backgroundColor: colors.card,
        surfaceTintColor: Colors.transparent,
        headerBackgroundColor: colors.actionPrimary,
        headerForegroundColor: LpgTokensLight.colorActionPrimaryText,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LpgRadius.xxl),
        ),
      ),
      extensions: [colors],
    );
  }

  static ThemeData get light => build(LpgThemeVariant.light);
  static ThemeData get dark => build(LpgThemeVariant.dark);
  static ThemeData get highContrast => build(LpgThemeVariant.highContrast);
}
