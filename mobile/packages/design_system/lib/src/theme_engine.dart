import 'package:flutter/material.dart';

import 'components/lpg_backdrop.dart';
import 'layout.dart';
import 'theme.dart';
import 'tokens.dart';

/// The one brand accent an app passes to the theme engine: highlights, the
/// brand mark and the "accent" tone. One colour per theme variant, because the
/// dark theme needs a lighter shade and high contrast needs one that clears
/// 4.5:1 on white.
@immutable
class LpgAccent {
  const LpgAccent({
    required this.light,
    required this.dark,
    required this.highContrast,
  });

  /// The brand's flame orange, today's accent in all three apps.
  static const flame = LpgAccent(
    light: LpgTokens.primitiveColorFlameOrange500,
    dark: LpgTokens.primitiveColorFlameOrange400,
    highContrast: LpgTokensHighContrast.colorActionPrimary,
  );

  /// The brand's gas blue, for an app that wants a calmer accent.
  static const gas = LpgAccent(
    light: LpgTokens.primitiveColorGasBlue500,
    dark: LpgTokens.primitiveColorGasBlue400,
    highContrast: LpgTokensHighContrast.colorActionPrimary,
  );

  final Color light;
  final Color dark;
  final Color highContrast;

  Color forVariant(LpgThemeVariant variant) => switch (variant) {
    LpgThemeVariant.light => light,
    LpgThemeVariant.dark => dark,
    LpgThemeVariant.highContrast => highContrast,
  };
}

/// Spacing that follows the window size class, read as `context.lpgDensity`.
///
/// Phones (compact) keep today's values exactly; wider windows step up so a
/// tablet does not look like a stretched phone. Screens migrate to it in the
/// tablet epic (E6); the engine provides it from now on.
@immutable
class LpgDensity extends ThemeExtension<LpgDensity> {
  const LpgDensity({
    required this.sizeClass,
    required this.pageGutter,
    required this.sectionGap,
    required this.cardPadding,
  });

  factory LpgDensity.forSizeClass(LpgSizeClass sizeClass) =>
      switch (sizeClass) {
        LpgSizeClass.compact => const LpgDensity(
          sizeClass: LpgSizeClass.compact,
          pageGutter: LpgSpacing.mdl,
          sectionGap: LpgSpacing.md,
          cardPadding: LpgSpacing.mdl,
        ),
        LpgSizeClass.medium => const LpgDensity(
          sizeClass: LpgSizeClass.medium,
          pageGutter: LpgSpacing.lg,
          sectionGap: LpgSpacing.mdl,
          cardPadding: LpgSpacing.lg,
        ),
        LpgSizeClass.expanded => const LpgDensity(
          sizeClass: LpgSizeClass.expanded,
          pageGutter: LpgSpacing.xl,
          sectionGap: LpgSpacing.lg,
          cardPadding: LpgSpacing.lg,
        ),
      };

  final LpgSizeClass sizeClass;
  final double pageGutter;
  final double sectionGap;
  final double cardPadding;

  @override
  LpgDensity copyWith({
    LpgSizeClass? sizeClass,
    double? pageGutter,
    double? sectionGap,
    double? cardPadding,
  }) => LpgDensity(
    sizeClass: sizeClass ?? this.sizeClass,
    pageGutter: pageGutter ?? this.pageGutter,
    sectionGap: sectionGap ?? this.sectionGap,
    cardPadding: cardPadding ?? this.cardPadding,
  );

  @override
  LpgDensity lerp(ThemeExtension<LpgDensity>? other, double t) {
    if (other is! LpgDensity) return this;
    double d(double a, double b) => a + (b - a) * t;
    return LpgDensity(
      sizeClass: t < 0.5 ? sizeClass : other.sizeClass,
      pageGutter: d(pageGutter, other.pageGutter),
      sectionGap: d(sectionGap, other.sectionGap),
      cardPadding: d(cardPadding, other.cardPadding),
    );
  }
}

extension LpgDensityContext on BuildContext {
  /// The density for the current window size class. Falls back to the phone
  /// values where no [LpgThemeEngine] is above (a bare `MaterialApp` in a
  /// test).
  LpgDensity get lpgDensity =>
      Theme.of(this).extension<LpgDensity>() ??
      LpgDensity.forSizeClass(LpgSizeClass.compact);
}

/// A [PageTransitionsTheme] with no movement: pages swap at once. Used when
/// the app is asked to reduce motion.
const lpgInstantPageTransitions = PageTransitionsTheme(
  builders: {
    TargetPlatform.android: LpgBackdropTransitions(
      _InstantPageTransitionsBuilder(),
    ),
    TargetPlatform.iOS: LpgBackdropTransitions(
      _InstantPageTransitionsBuilder(),
    ),
    TargetPlatform.macOS: LpgBackdropTransitions(
      _InstantPageTransitionsBuilder(),
    ),
    TargetPlatform.linux: LpgBackdropTransitions(
      _InstantPageTransitionsBuilder(),
    ),
    TargetPlatform.windows: LpgBackdropTransitions(
      _InstantPageTransitionsBuilder(),
    ),
    TargetPlatform.fuchsia: LpgBackdropTransitions(
      _InstantPageTransitionsBuilder(),
    ),
  },
);

class _InstantPageTransitionsBuilder extends PageTransitionsBuilder {
  const _InstantPageTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) => child;
}

/// Caps the text scale of [child] at [max], for layouts that cannot reflow
/// (dense tables, fixed-height rows). Everything else follows the person's
/// setting up to the engine's own limit.
class LpgTextScaleLimit extends StatelessWidget {
  const LpgTextScaleLimit({super.key, this.max = 1.3, required this.child});

  final double max;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final query = MediaQuery.of(context);
    return MediaQuery(
      data: query.copyWith(
        textScaler: query.textScaler.clamp(maxScaleFactor: max),
      ),
      child: child,
    );
  }
}

/// The single place an app's look is configured. An app creates one engine
/// with its accent and flags and hands its themes and [builder] to
/// `MaterialApp`; it never builds a `ThemeData` of its own.
///
/// ```dart
/// final engine = LpgThemeEngine();
/// MaterialApp(
///   theme: engine.light,
///   darkTheme: engine.dark,
///   highContrastTheme: engine.highContrast,
///   highContrastDarkTheme: engine.highContrast,
///   builder: engine.builder,
/// )
/// ```
///
/// What it owns:
/// - **Variants**: light, dark and high contrast, all from the one token
///   source (the platform picks the variant through `MaterialApp`).
/// - **Accent**: [accent], per app.
/// - **Density by size class**: [LpgDensity] in the theme, chosen from the
///   window width.
/// - **Text scale**: the person's setting is honoured up to [maxTextScale];
///   beyond that layouts would break rather than help.
/// - **Reduce motion**: follows the platform setting, or is forced on with
///   [reduceMotion]; page transitions become instant and every `LpgMotion`
///   duration collapses.
@immutable
class LpgThemeEngine {
  const LpgThemeEngine({
    this.accent = LpgAccent.flame,
    this.maxTextScale = 2.0,
    this.reduceMotion = false,
  });

  final LpgAccent accent;

  /// The largest text scale factor any screen sees.
  final double maxTextScale;

  /// Force reduced motion on, whatever the platform says.
  final bool reduceMotion;

  ThemeData _build(LpgThemeVariant variant) =>
      LpgTheme.build(variant, accent: accent, reduceMotion: reduceMotion);

  ThemeData get light => _build(LpgThemeVariant.light);
  ThemeData get dark => _build(LpgThemeVariant.dark);
  ThemeData get highContrast => _build(LpgThemeVariant.highContrast);

  /// For `MaterialApp.builder`: applies the text-scale limit, the reduce-motion
  /// flag and the density for the current window width.
  Widget builder(BuildContext context, Widget? child) {
    final query = MediaQuery.of(context);
    final theme = Theme.of(context);
    final density = LpgDensity.forSizeClass(LpgSizeClass.of(context));
    final reduce = reduceMotion || query.disableAnimations;

    return MediaQuery(
      data: query.copyWith(
        textScaler: query.textScaler.clamp(maxScaleFactor: maxTextScale),
        disableAnimations: reduce,
      ),
      child: Theme(
        data: theme.copyWith(
          // The platform setting can change while the app runs, so the page
          // transitions are chosen here, not only when the theme is built.
          pageTransitionsTheme: reduce
              ? lpgInstantPageTransitions
              : theme.pageTransitionsTheme,
          extensions: [
            ...theme.extensions.values.where((e) => e is! LpgDensity),
            density,
          ],
        ),
        child: child ?? const SizedBox.shrink(),
      ),
    );
  }
}
