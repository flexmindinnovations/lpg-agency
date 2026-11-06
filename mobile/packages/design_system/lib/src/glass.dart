import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'components/lpg_backdrop.dart';
import 'layout.dart';
import 'surface.dart';
import 'theme.dart';

/// How see-through glass surfaces are, worked out from the theme's own colours
/// the same way the page's washes are (see [LpgBackdropLook]): the **most
/// transparent** fill that still keeps primary and secondary text at 4.5:1 or
/// better on the worst thing that can be behind it.
///
/// * A card sits on the page, so the worst thing behind it is the page's worst
///   pixel (a wash at its strongest, a grain speck on top).
/// * A frosted sheet sits over arbitrary content, blurred. The worst blurred
///   content is an average of whatever is under it, which can be no darker than
///   black or lighter than white, so those two are the worst case.
///
/// So a theme with little room (dark text on a dark-ish page) gets a more
/// opaque glass, and it loosens by itself if a text colour is improved. High
/// contrast is not glass at all: fully opaque.
@immutable
class LpgGlassLook {
  const LpgGlassLook({required this.cardAlpha, required this.sheetAlpha});

  /// Opacity of a card's fill, 0 to 1.
  final double cardAlpha;

  /// Opacity of a frosted sheet's fill, 0 to 1.
  final double sheetAlpha;

  /// What each would like to be if contrast allowed it.
  static const cardTarget = 0.62;
  static const sheetTarget = 0.78;

  /// How much the backdrop behind a frosted sheet is blurred, in logical px.
  static const blurSigma = 22.0;

  static final Expando<LpgGlassLook> _cache = Expando();

  static LpgGlassLook of(LpgColors colors) =>
      _cache[colors] ??= _compute(colors);

  static LpgGlassLook _compute(LpgColors colors) {
    if (colors.isHighContrast) {
      return const LpgGlassLook(cardAlpha: 1, sheetAlpha: 1);
    }

    final page = LpgBackdropLook.of(colors);
    final pageSamples = <Color>[
      for (final c in [
        colors.canvas,
        page.base,
        ...page.washes.map((w) => w.color),
      ])
        colors.tint(page.speck, page.grainStrength, over: c),
    ];
    const extremes = [Color(0xFF000000), Color(0xFFFFFFFF)];

    return LpgGlassLook(
      cardAlpha: _smallest(cardTarget, colors.card, pageSamples, colors),
      sheetAlpha: _smallest(sheetTarget, colors.sheet, extremes, colors),
    );
  }

  /// The smallest opacity from [target] up to 1 at which text stays readable
  /// on [fill] laid over every one of [behind].
  static double _smallest(
    double target,
    Color fill,
    List<Color> behind,
    LpgColors colors,
  ) {
    bool readable(double alpha) {
      for (final back in behind) {
        final glass = Color.alphaBlend(fill.withValues(alpha: alpha), back);
        for (final text in [colors.textPrimary, colors.textSecondary]) {
          if (LpgBackdropLook.contrast(text, glass) <
              LpgBackdropLook.minTextContrast) {
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
      other.sheetAlpha == sheetAlpha;

  @override
  int get hashCode => Object.hash(cardAlpha, sheetAlpha);
}

extension LpgGlassColors on LpgColors {
  /// The see-through fill of a card (or the nav bar): [card] at the opacity
  /// [LpgGlassLook] allows. Opaque in high contrast.
  Color get cardGlass =>
      card.withValues(alpha: LpgGlassLook.of(this).cardAlpha);

  /// The see-through fill of a frosted sheet. Only ever use it together with a
  /// blur (see [LpgGlass]): on its own, content behind it would show through.
  Color get sheetGlass =>
      sheet.withValues(alpha: LpgGlassLook.of(this).sheetAlpha);
}

/// A surface's resting shadow, drawn **outside** the shape only.
///
/// A `BoxDecoration` shadow is painted under the whole box, so behind a
/// see-through fill it would show through as a grey patch inside the card.
/// This paints the same shadow with the shape cut out of it.
class LpgGlassShadow extends StatelessWidget {
  const LpgGlassShadow({
    super.key,
    required this.shadows,
    required this.radius,
    required this.child,
  });

  final List<BoxShadow> shadows;
  final BorderRadius radius;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (shadows.isEmpty) return child;
    return CustomPaint(
      painter: _OutsideShadowPainter(shadows, radius),
      child: child,
    );
  }
}

class _OutsideShadowPainter extends CustomPainter {
  _OutsideShadowPainter(this.shadows, this.radius);

  final List<BoxShadow> shadows;
  final BorderRadius radius;

  @override
  void paint(Canvas canvas, Size size) {
    final box = radius.toRRect(Offset.zero & size);
    final everything = Path()..addRect((Offset.zero & size).inflate(160));
    final outside = Path.combine(
      PathOperation.difference,
      everything,
      Path()..addRRect(box),
    );
    canvas.save();
    canvas.clipPath(outside);
    for (final shadow in shadows) {
      canvas.drawRRect(
        box.shift(shadow.offset).inflate(shadow.spreadRadius),
        shadow.toPaint(),
      );
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_OutsideShadowPainter old) =>
      old.radius != radius || !_same(old.shadows, shadows);

  static bool _same(List<BoxShadow> a, List<BoxShadow> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
}

/// A frosted-glass container: a see-through fill, a hairline, and (when
/// [blur] is on) the content behind it blurred.
///
/// Blur only belongs where there is something to blur: a sheet or panel over
/// scrolling content. A card on the page is already over a soft, static
/// backdrop, so cards use [LpgSurface] (see-through, no blur) and skip the
/// per-frame cost of a backdrop filter in every list row.
///
/// Without [blur] the fill is the card glass, which is safe only over the page;
/// with [blur] it is the stronger sheet glass, sized for any content behind.
/// In high contrast both are fully opaque and nothing is blurred.
class LpgGlass extends StatelessWidget {
  const LpgGlass({
    super.key,
    required this.child,
    this.level = LpgSurfaceLevel.sheet,
    this.blur = true,
    this.padding,
    this.radius,
    this.shadow = true,
  });

  final Widget child;
  final LpgSurfaceLevel level;
  final bool blur;
  final EdgeInsetsGeometry? padding;
  final BorderRadius? radius;
  final bool shadow;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final shape = radius ?? LpgSurface.radiusFor(level);
    final content = padding == null
        ? child
        : Padding(padding: padding!, child: child);

    if (colors.isHighContrast) {
      return LpgSurface(
        level: level,
        radius: shape,
        shadow: shadow,
        child: content,
      );
    }

    Widget panel = DecoratedBox(
      decoration: BoxDecoration(
        color: blur ? colors.sheetGlass : colors.cardGlass,
        borderRadius: shape,
        border: Border.fromBorderSide(colors.hairlineFor(level)),
      ),
      child: content,
    );
    if (blur) {
      panel = ClipRRect(
        borderRadius: shape,
        child: BackdropFilter(
          filter: ui.ImageFilter.blur(
            sigmaX: LpgGlassLook.blurSigma,
            sigmaY: LpgGlassLook.blurSigma,
            tileMode: TileMode.clamp,
          ),
          child: panel,
        ),
      );
    }
    return LpgGlassShadow(
      shadows: shadow ? colors.shadowFor(level) : const [],
      radius: shape,
      child: panel,
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
