import 'package:flutter/material.dart';

import 'glass.dart';
import 'layout.dart';
import 'theme.dart';

/// The solid layers every surface belongs to, lowest to highest.
///
/// Depth is made of **tone**, **soft shadow** and a **1 px hairline**. Light
/// themes step mostly by shadow (white cards on a faintly tinted canvas), dark
/// themes by tone (each level a lighter fill), and high contrast by a 2 px
/// border with no shadow.
///
/// Cards are frosted glass: slightly see-through and lightly blurred, with a
/// fine grain, so the paper page shows softly through them (see `LpgGlassLook`); sheets are frosted glass (see `LpgGlass`) when they
/// float over content and solid otherwise. Every other level, and every level
/// in high contrast, is a solid fill.
enum LpgSurfaceLevel {
  /// The page behind everything.
  canvas,

  /// Cards, list groups, input fields: the default container.
  card,

  /// Things that float above cards: bottom sheets, dialogs, menus.
  sheet,

  /// Snackbars and toasts: dark on light themes, light on dark themes.
  inverse,
}

extension LpgSurfaceColors on LpgColors {
  /// The solid fill of [level].
  Color surfaceFor(LpgSurfaceLevel level) => switch (level) {
    LpgSurfaceLevel.canvas => canvas,
    LpgSurfaceLevel.card => card,
    LpgSurfaceLevel.sheet => sheet,
    LpgSurfaceLevel.inverse => inverse,
  };

  /// The resting shadow of [level] (none in high contrast, where the border
  /// separates instead).
  List<BoxShadow> shadowFor(LpgSurfaceLevel level) => switch (level) {
    LpgSurfaceLevel.canvas => const [],
    LpgSurfaceLevel.card => cardShadow,
    LpgSurfaceLevel.sheet || LpgSurfaceLevel.inverse => floatingShadow,
  };

  /// The 1 px hairline that separates a surface from what is behind it: 2 px
  /// and stronger in high contrast, absent on the inverse level.
  BorderSide hairlineFor(LpgSurfaceLevel level) {
    if (level == LpgSurfaceLevel.inverse || level == LpgSurfaceLevel.canvas) {
      return BorderSide.none;
    }
    return isHighContrast
        ? BorderSide(color: borderStrong, width: 2)
        : BorderSide(color: outline);
  }
}

/// A container drawn from the surface system: [level]'s fill, hairline and
/// shadow, with the radius that level uses (cards 18 px, sheets 24 px). A card
/// is see-through (the page shows softly through it); other levels are solid.
///
/// Use this instead of hand-building a `DecoratedBox` with a colour, so every
/// custom surface follows the theme in all three variants.
class LpgSurface extends StatelessWidget {
  const LpgSurface({
    super.key,
    required this.child,
    this.level = LpgSurfaceLevel.card,
    this.padding,
    this.radius,
    this.shadow = true,
  });

  final Widget child;
  final LpgSurfaceLevel level;
  final EdgeInsetsGeometry? padding;

  /// Defaults to the level's radius.
  final BorderRadius? radius;

  /// Draw the level's soft shadow (nested surfaces turn it off).
  final bool shadow;

  static BorderRadius radiusFor(LpgSurfaceLevel level) => switch (level) {
    LpgSurfaceLevel.sheet => BorderRadius.circular(LpgRadius.xxl),
    LpgSurfaceLevel.inverse => BorderRadius.circular(LpgRadius.lg),
    _ => LpgRadius.cardRadius,
  };

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final shape = radius ?? radiusFor(level);
    // A card is frosted glass: see-through, lightly blurred, with a fine
    // grain. Its shadow is drawn outside its shape (see LpgGlass), because a
    // shadow behind a see-through fill would show through it.
    if (level == LpgSurfaceLevel.card && !colors.isHighContrast) {
      return LpgGlass(
        level: level,
        radius: shape,
        shadow: shadow,
        padding: padding,
        child: child,
      );
    }
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.surfaceFor(level),
        borderRadius: shape,
        border: Border.fromBorderSide(colors.hairlineFor(level)),
        boxShadow: shadow ? colors.shadowFor(level) : null,
      ),
      child: padding == null ? child : Padding(padding: padding!, child: child),
    );
  }
}
