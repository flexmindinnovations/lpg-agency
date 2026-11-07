import 'package:flutter/material.dart';

import 'components/lpg_backdrop.dart';
import 'layout.dart';
import 'surface.dart';
import 'theme.dart';

/// How see-through glass surfaces are, worked out from the theme's own colours
/// the same way the page's grain is (see [LpgBackdropLook]): the **most
/// transparent** fill that still keeps primary and secondary text at 4.5:1 or
/// better on the worst thing that can be behind it.
///
/// Cards, fields, chips and bars sit on the page, so the worst thing behind
/// them is the page's worst pixel (a wash at its strongest, a grain speck on
/// top). They carry no texture of their own: the page's paper shows through the
/// fill, which is the one place the background is painted. A theme with little
/// room (dark text on a dark-ish page) gets a more opaque fill, and it loosens
/// by itself if a text colour is improved. High contrast is not glass at all:
/// fully opaque.
@immutable
class LpgGlassLook {
  const LpgGlassLook({required this.cardAlpha, this.barAlpha = 1});

  /// Opacity of a card's fill, 0 to 1.
  final double cardAlpha;

  /// Opacity of a bar's fill (the navigation bar, the header once the page is
  /// scrolled), 0 to 1. A bar holds only short, bold labels and icons, so it is
  /// more see-through than a card.
  final double barAlpha;

  /// What each would like to be if contrast allowed it. Lower means more of the
  /// page shows through; this is the knob for how much background a card lets
  /// by.
  static const cardTarget = 0.6;
  static const barTarget = 0.4;

  /// What text on a card, field or chip keeps. They sit on the page, so they
  /// are held to what the page itself is: as readable as the page under them.
  static const cardContrast = LpgBackdropLook.minTextContrast;

  /// What a bar's text and icons keep (WCAG AA for normal text).
  static const barContrast = LpgBackdropLook.minTextContrast;

  static final Expando<LpgGlassLook> _cache = Expando();

  static LpgGlassLook of(LpgColors colors) =>
      _cache[colors] ??= _compute(colors);

  static LpgGlassLook _compute(LpgColors colors) {
    if (colors.isHighContrast) {
      return const LpgGlassLook(cardAlpha: 1, barAlpha: 1);
    }

    final page = LpgBackdropLook.of(colors);
    final pageSamples = <Color>[
      for (final c in [colors.canvas, ...page.samples])
        colors.tint(page.speck, page.grainStrength, over: c),
    ];

    return LpgGlassLook(
      cardAlpha: _smallest(cardTarget, colors, pageSamples, cardContrast),
      barAlpha: _smallest(barTarget, colors, pageSamples, barContrast),
    );
  }

  /// The smallest opacity from [target] up to 1 at which text stays at
  /// [minContrast] on the card colour laid over every one of [behind].
  static double _smallest(
    double target,
    LpgColors colors,
    List<Color> behind,
    double minContrast,
  ) {
    bool readable(double alpha) {
      for (final back in behind) {
        final glass = Color.alphaBlend(
          colors.card.withValues(alpha: alpha),
          back,
        );
        for (final text in [colors.textPrimary, colors.textSecondary]) {
          if (LpgBackdropLook.contrast(text, glass) < minContrast) {
            return false;
          }
        }
      }
      return true;
    }

    if (readable(target)) return target;
    var lo = target;
    var hi = 1.0;
    for (var i = 0; i < 14; i++) {
      final mid = (lo + hi) / 2;
      if (readable(mid)) {
        hi = mid;
      } else {
        lo = mid;
      }
    }
    return hi;
  }

  @override
  bool operator ==(Object other) =>
      other is LpgGlassLook &&
      other.cardAlpha == cardAlpha &&
      other.barAlpha == barAlpha;

  @override
  int get hashCode => Object.hash(cardAlpha, barAlpha);
}

extension LpgGlassColors on LpgColors {
  /// The see-through fill of a card (or the nav bar): [card] at the opacity
  /// [LpgGlassLook] allows. Opaque in high contrast.
  Color get cardGlass =>
      card.withValues(alpha: LpgGlassLook.of(this).cardAlpha);

  /// The see-through fill of a bar: the navigation bar, and the header once the
  /// page is scrolled. Lighter than a card's (see [LpgGlassLook.barAlpha]).
  Color get barGlass => card.withValues(alpha: LpgGlassLook.of(this).barAlpha);
}

/// A glass container. At card level it is a see-through fill and a hairline
/// laid over the page: nothing is blurred and it has no texture of its own, so
/// the page's paper shows through. At sheet level (it floats over the screen,
/// so it cannot rely on what is behind it) it is the paper itself: a fresh
/// [LpgBackdrop] inside the rounded sheet, so a sheet looks like the page it
/// slides over. In high contrast both are plain opaque surfaces.
///
/// There is no backdrop blur anywhere: redrawing one every frame of a scroll or
/// a sheet's slide is what made them drop frames.
class LpgGlass extends StatelessWidget {
  const LpgGlass({
    super.key,
    required this.child,
    this.level = LpgSurfaceLevel.sheet,
    this.padding,
    this.radius,
  });

  final Widget child;
  final LpgSurfaceLevel level;
  final EdgeInsetsGeometry? padding;
  final BorderRadius? radius;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final shape = radius ?? LpgSurface.radiusFor(level);
    final content = padding == null
        ? child
        : Padding(padding: padding!, child: child);

    if (colors.isHighContrast) {
      return LpgSurface(level: level, radius: shape, child: content);
    }

    final border = Border.fromBorderSide(colors.hairlineFor(level));
    if (level == LpgSurfaceLevel.card) {
      return ClipRRect(
        borderRadius: shape,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: colors.cardGlass,
            borderRadius: shape,
            border: border,
          ),
          child: content,
        ),
      );
    }
    return ClipRRect(
      borderRadius: shape,
      child: DecoratedBox(
        // The hairline goes over the paper, which is opaque.
        position: DecorationPosition.foreground,
        decoration: BoxDecoration(borderRadius: shape, border: border),
        child: LpgBackdrop(child: content),
      ),
    );
  }
}

/// The small grab handle at the top of a frosted sheet. Drawn here rather
/// than by the platform sheet so it sits *inside* the glass.
class LpgSheetHandle extends StatelessWidget {
  const LpgSheetHandle({super.key});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      button: true,
      label: 'Dismiss',
      onTap: () => Navigator.of(context).maybePop(),
      excludeSemantics: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => Navigator.of(context).maybePop(),
        child: SizedBox(
          height: LpgSizes.touchTarget,
          child: Center(
            child: Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: context.lpgColors.borderStrong,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
