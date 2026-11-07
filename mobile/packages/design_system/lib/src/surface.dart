import 'package:flutter/material.dart';

import 'glass.dart';
import 'layout.dart';
import 'theme.dart';

/// The solid layers every surface belongs to, lowest to highest.
///
/// Depth is made of **tone** and a **1 px hairline**; there are no shadows (5.18).
/// Cards are see-through, so the paper page and its grain show through them
/// (see `LpgGlassLook`); sheets are frosted glass (see `LpgGlass`) when they
/// float over content and solid otherwise. Every other level, and every level
/// in high contrast (which uses a 2 px border), is a solid fill.
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

/// A container drawn from the surface system: [level]'s fill and hairline,
/// with the radius that level uses (cards 18 px, sheets 24 px). A card
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
  });

  final Widget child;
  final LpgSurfaceLevel level;
  final EdgeInsetsGeometry? padding;

  /// Defaults to the level's radius.
  final BorderRadius? radius;

  static BorderRadius radiusFor(LpgSurfaceLevel level) => switch (level) {
    LpgSurfaceLevel.sheet => BorderRadius.circular(LpgRadius.xxl),
    LpgSurfaceLevel.inverse => BorderRadius.circular(LpgRadius.lg),
    _ => LpgRadius.cardRadius,
  };

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final shape = radius ?? radiusFor(level);
    // A card is see-through: the page and its grain show through it.
    if (level == LpgSurfaceLevel.card && !colors.isHighContrast) {
      return LpgGlass(
        level: level,
        radius: shape,
        padding: padding,
        child: child,
      );
    }
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.surfaceFor(level),
        borderRadius: shape,
        border: Border.fromBorderSide(colors.hairlineFor(level)),
      ),
      child: padding == null ? child : Padding(padding: padding!, child: child),
    );
  }
}
