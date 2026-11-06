import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'components/lpg_backdrop.dart';
import 'grain.dart';
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
  const LpgGlassLook({
    required this.cardAlpha,
    required this.sheetAlpha,
    this.barAlpha = 1,
  });

  /// Opacity of a card's fill, 0 to 1.
  final double cardAlpha;

  /// Opacity of a frosted sheet's fill, 0 to 1.
  final double sheetAlpha;

  /// Opacity of a bar's fill (the navigation bar, the header once the page is
  /// scrolled), 0 to 1. A bar holds only short, bold labels and icons, so it is
  /// sized to AA's 4.5:1 rather than the 6:1 of a card and is more see-through.
  final double barAlpha;

  /// What each would like to be if contrast allowed it.
  static const cardTarget = 0.55;
  static const barTarget = 0.4;
  static const sheetTarget = 0.78;

  /// How much the backdrop behind a frosted sheet is blurred, in logical px.
  static const blurSigma = 22.0;

  /// How much a card blurs what is behind it. Less than a sheet: behind a card
  /// there is only the soft page, and a light blur is enough to melt the
  /// small orbs into it.
  static const cardBlurSigma = 14.0;

  /// How much of the grain is laid under a card's fill, 0 to 1 (it shows
  /// through the see-through fill at roughly half this). The grain is under the
  /// fill and so never touches text; the opacity search below still counts a
  /// speck at this strength in what the fill is laid over. A sheet floats over
  /// arbitrary content, so it has less room and a finer grain.
  static const grainStrength = 0.2;
  static const sheetGrainStrength = 0.08;

  /// Text on glass keeps this contrast on the worst
  /// pixel behind it, so it reads crisply, not just legally. Well above the
  /// 4.5:1 the page itself is held to.
  static const readableContrast = 6.0;

  /// What a bar's text and icons keep (WCAG AA for normal text).
  static const barContrast = LpgBackdropLook.minTextContrast;

  static final Expando<LpgGlassLook> _cache = Expando();

  static LpgGlassLook of(LpgColors colors) =>
      _cache[colors] ??= _compute(colors);

  static LpgGlassLook _compute(LpgColors colors) {
    if (colors.isHighContrast) {
      return const LpgGlassLook(cardAlpha: 1, sheetAlpha: 1, barAlpha: 1);
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
      cardAlpha: _smallest(
        cardTarget,
        colors.card,
        pageSamples,
        colors,
        page.speck,
        grainStrength,
      ),
      sheetAlpha: _smallest(
        sheetTarget,
        colors.sheet,
        extremes,
        colors,
        page.speck,
        sheetGrainStrength,
      ),
      barAlpha: _smallest(
        barTarget,
        colors.card,
        pageSamples,
        colors,
        page.speck,
        grainStrength,
        minContrast: barContrast,
      ),
    );
  }

  /// The smallest opacity from [target] up to 1 at which text stays readable
  /// on [fill] laid over every one of [behind], with a grain [speck] under it.
  static double _smallest(
    double target,
    Color fill,
    List<Color> behind,
    LpgColors colors,
    Color speck,
    double grain, {
    double minContrast = readableContrast,
  }) {
    bool readable(double alpha) {
      for (final back in behind) {
        // The grain sits under the fill (never over the text), so it is part
        // of what the fill is laid over.
        final glass = Color.alphaBlend(
          fill.withValues(alpha: alpha),
          colors.tint(speck, grain, over: back),
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
      other.sheetAlpha == sheetAlpha &&
      other.barAlpha == barAlpha;

  @override
  int get hashCode => Object.hash(cardAlpha, sheetAlpha, barAlpha);
}

extension LpgGlassColors on LpgColors {
  /// The see-through fill of a card (or the nav bar): [card] at the opacity
  /// [LpgGlassLook] allows. Opaque in high contrast.
  Color get cardGlass =>
      card.withValues(alpha: LpgGlassLook.of(this).cardAlpha);

  /// The see-through fill of a bar: the navigation bar, and the header once the
  /// page is scrolled. Lighter than a card's (see [LpgGlassLook.barAlpha]).
  Color get barGlass => card.withValues(alpha: LpgGlassLook.of(this).barAlpha);

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

/// Frosted glass, the layers every glass surface is made of: whatever is
/// behind it blurred by [blurSigma] (none when `null`), then [child] (the
/// fill, hairline and content), then a fine grain over the top.
///
/// Clips to [radius]. This is the one place a backdrop filter or grain is
/// laid over a surface, so a card, a sheet and a custom panel all look alike.
class LpgGlassPane extends StatefulWidget {
  const LpgGlassPane({
    super.key,
    required this.radius,
    required this.child,
    this.blurSigma,
    this.grain = LpgGlassLook.grainStrength,
  });

  final BorderRadius radius;
  final double? blurSigma;

  /// How much of the grain shows over the top, 0 to 1.
  final double grain;
  final Widget child;

  @override
  State<LpgGlassPane> createState() => _LpgGlassPaneState();
}

class _LpgGlassPaneState extends State<LpgGlassPane> {
  @override
  void initState() {
    super.initState();
    LpgGrain.ensureLoaded();
  }

  @override
  Widget build(BuildContext context) {
    Widget pane = Stack(
      fit: StackFit.passthrough,
      children: [
        // Under the content, never over it: the grain must not touch text.
        Positioned.fill(
          child: ExcludeSemantics(
            child: IgnorePointer(
              child: ValueListenableBuilder<ui.Image?>(
                valueListenable: LpgGrain.image,
                builder: (context, tile, _) => tile == null || widget.grain <= 0
                    ? const SizedBox.shrink()
                    : CustomPaint(painter: _GrainPainter(tile, widget.grain)),
              ),
            ),
          ),
        ),
        widget.child,
      ],
    );
    final sigma = widget.blurSigma;
    if (sigma != null) {
      pane = BackdropFilter(
        filter: ui.ImageFilter.blur(
          sigmaX: sigma,
          sigmaY: sigma,
          tileMode: TileMode.clamp,
        ),
        child: pane,
      );
    }
    return ClipRRect(borderRadius: widget.radius, child: pane);
  }
}

class _GrainPainter extends CustomPainter {
  _GrainPainter(this.tile, this.strength);

  final ui.Image tile;
  final double strength;

  @override
  void paint(Canvas canvas, Size size) =>
      LpgGrain.paint(canvas, Offset.zero & size, tile, strength);

  @override
  bool shouldRepaint(_GrainPainter old) =>
      old.tile != tile || old.strength != strength;
}

/// A frosted-glass container: a see-through fill, a hairline, the content
/// behind it blurred (when [blur] is on) and a fine grain over the top.
///
/// A card-level glass blurs lightly ([LpgGlassLook.cardBlurSigma]) with the
/// card fill; a sheet-level glass blurs strongly ([LpgGlassLook.blurSigma])
/// with the stronger sheet fill, sized for any content behind. Without [blur]
/// the fill is the card glass, which is safe only over the page. In high
/// contrast both are fully opaque and nothing is blurred.
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

    final isCard = level == LpgSurfaceLevel.card;
    final panel = LpgGlassPane(
      radius: shape,
      grain: isCard
          ? LpgGlassLook.grainStrength
          : LpgGlassLook.sheetGrainStrength,
      blurSigma: !blur
          ? null
          : isCard
          ? LpgGlassLook.cardBlurSigma
          : LpgGlassLook.blurSigma,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: blur && !isCard ? colors.sheetGlass : colors.cardGlass,
          borderRadius: shape,
          border: Border.fromBorderSide(colors.hairlineFor(level)),
        ),
        child: content,
      ),
    );
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
