import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'components/lpg_backdrop.dart';
import 'grain.dart';
import 'layout.dart';
import 'surface.dart';
import 'theme.dart';

/// How see-through glass surfaces are, worked out from the theme's own colours
/// the same way the page's grain is (see [LpgBackdropLook]): the **most
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
    this.surfaceGrain = 0,
    this.sheetGrain = 0,
  });

  /// Opacity of a card's fill, 0 to 1.
  final double cardAlpha;

  /// Opacity of a frosted sheet's fill, 0 to 1.
  final double sheetAlpha;

  /// Opacity of a bar's fill (the navigation bar, the header once the page is
  /// scrolled), 0 to 1. A bar holds only short, bold labels and icons, so it is
  /// sized to AA's 4.5:1 rather than the 6:1 of a card and is more see-through.
  final double barAlpha;

  /// How much grain is laid over a card's, field's, chip's or secondary
  /// button's fill, under its content, 0 to 1: the most that still keeps text
  /// at [cardContrast] on the worst pixel (see [LpgGrainLayer]).
  final double surfaceGrain;

  /// The same for a frosted sheet's fill.
  final double sheetGrain;

  /// What each would like to be if contrast allowed it.
  static const cardTarget = 0.6;
  static const barTarget = 0.4;
  static const sheetTarget = 0.78;

  /// How much the backdrop behind a frosted sheet is blurred, in logical px.
  static const blurSigma = 22.0;

  /// How much of the grain is laid under a bar's or sheet's fill, 0 to 1. A
  /// card has none of its own: the page's grain shows through its fill. The
  /// grain is under the fill and so never touches text; the opacity search
  /// below still counts a speck at this strength in what the fill is laid
  /// over. A sheet floats over arbitrary content, so it has less room and a
  /// finer grain.
  static const grainStrength = 0.2;

  /// What grain a solid control (a filled button) carries. Its fill is known
  /// and dark or strongly tinted, so a light touch keeps its label crisp.
  static const solidGrain = 0.1;

  /// Text on a sheet keeps this contrast on the worst pixel behind it, so it
  /// reads crisply, not just legally. Well above the 4.5:1 the page itself is
  /// held to.
  static const readableContrast = 6.0;

  /// What text on a card, field or chip keeps. They sit on the page, so they
  /// are held to what the page itself is: as readable as the page under them.
  /// The fill is [cardTarget] opaque (the paper's grain shows through softly)
  /// or more if the page behind it needs it.
  static const cardContrast = LpgBackdropLook.minTextContrast;

  /// What text on a sheet keeps once the grain is over its fill.
  static const sheetContrast = LpgBackdropLook.minTextContrast;

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
      for (final c in [colors.canvas, page.base])
        colors.tint(page.speck, page.grainStrength, over: c),
    ];
    const extremes = [Color(0xFF000000), Color(0xFFFFFFFF)];

    final cardAlpha = _smallest(
      cardTarget,
      colors.card,
      pageSamples,
      colors,
      page.speck,
      0,
      minContrast: cardContrast,
    );
    final sheetAlpha = _smallest(
      sheetTarget,
      colors.sheet,
      extremes,
      colors,
      page.speck,
      0,
    );

    return LpgGlassLook(
      cardAlpha: cardAlpha,
      sheetAlpha: sheetAlpha,
      surfaceGrain: _grainOver(
        colors.card.withValues(alpha: cardAlpha),
        pageSamples,
        colors,
        page.speck,
        cardContrast,
      ),
      sheetGrain: _grainOver(
        colors.sheet.withValues(alpha: sheetAlpha),
        extremes,
        colors,
        page.speck,
        sheetContrast,
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

  /// The most grain, up to [grainStrength], that can be laid over [fill]
  /// (itself laid over each of [behind]) while text keeps [minContrast] on the
  /// worst pixel: a [speck] at that strength on top of the blended fill.
  static double _grainOver(
    Color fill,
    List<Color> behind,
    LpgColors colors,
    Color speck,
    double minContrast,
  ) => LpgBackdropLook.largest(grainStrength, (s) {
    for (final back in behind) {
      final glass = colors.tint(speck, s, over: Color.alphaBlend(fill, back));
      for (final text in [colors.textPrimary, colors.textSecondary]) {
        if (LpgBackdropLook.contrast(text, glass) < minContrast) return false;
      }
    }
    return true;
  });

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
      other.barAlpha == barAlpha &&
      other.surfaceGrain == surfaceGrain &&
      other.sheetGrain == sheetGrain;

  @override
  int get hashCode =>
      Object.hash(cardAlpha, sheetAlpha, barAlpha, surfaceGrain, sheetGrain);
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

/// Frosted glass, the layers a sheet or bar is made of: whatever is behind it
/// blurred by [blurSigma] (none when `null`), then a fine grain, then [child]
/// (the fill, hairline and content).
///
/// Clips to [radius]. This is the one place a backdrop filter or grain is
/// laid under a surface's content. Cards do not use it: a backdrop blur per
/// card, repeated every frame while a list scrolls, is what made scrolling
/// drop frames.
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
  _GrainPainter(this.tile, this.strength, [this.shape]);

  final ui.Image tile;
  final double strength;
  final ShapeBorder? shape;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final clip = shape;
    if (clip != null) canvas.clipPath(clip.getOuterPath(rect));
    LpgGrain.paint(canvas, rect, tile, strength);
  }

  @override
  bool shouldRepaint(_GrainPainter old) =>
      old.tile != tile || old.strength != strength || old.shape != shape;
}

/// The paper grain laid over a fill and under [child]'s content: a button, a
/// chip, a card or a sheet carries the same texture the page does.
///
/// Put it **inside** the fill (a `Material`'s or `DecoratedBox`'s child) so the
/// grain is over the colour and the label, icon or text is over the grain: the
/// grain never touches the content. It is one extra textured rectangle per
/// surface (no blur, no offscreen layer), which is what keeps scrolling smooth.
/// [strength] is worked out per surface in [LpgGlassLook] so text stays at
/// 4.5:1 or better. Pass [shape] when the fill is not clipped by an ancestor.
/// Nothing in high contrast.
class LpgGrainLayer extends StatefulWidget {
  const LpgGrainLayer({
    super.key,
    required this.strength,
    required this.child,
    this.shape,
  });

  final double strength;
  final ShapeBorder? shape;
  final Widget child;

  @override
  State<LpgGrainLayer> createState() => _LpgGrainLayerState();
}

class _LpgGrainLayerState extends State<LpgGrainLayer> {
  @override
  void initState() {
    super.initState();
    LpgGrain.ensureLoaded();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.strength <= 0 || context.lpgColors.isHighContrast) {
      return widget.child;
    }
    return Stack(
      fit: StackFit.passthrough,
      children: [
        Positioned.fill(
          child: ExcludeSemantics(
            child: IgnorePointer(
              child: ValueListenableBuilder<ui.Image?>(
                valueListenable: LpgGrain.image,
                builder: (context, tile, _) => tile == null
                    ? const SizedBox.shrink()
                    : CustomPaint(
                        painter: _GrainPainter(
                          tile,
                          widget.strength,
                          widget.shape,
                        ),
                      ),
              ),
            ),
          ),
        ),
        widget.child,
      ],
    );
  }
}

/// A frosted-glass container: a see-through fill, a hairline, the content
/// behind it blurred (when [blur] is on) and a fine grain over the top.
///
/// A card-level glass is only the see-through fill and hairline, laid over the
/// page, whose grain shows through; nothing is blurred. A sheet-level glass
/// blurs strongly ([LpgGlassLook.blurSigma]) with the stronger sheet fill,
/// sized for any content behind. Without [blur] the fill is the card glass,
/// which is safe only over the page. In high contrast both are fully opaque
/// and nothing is blurred.
class LpgGlass extends StatelessWidget {
  const LpgGlass({
    super.key,
    required this.child,
    this.level = LpgSurfaceLevel.sheet,
    this.blur = true,
    this.padding,
    this.radius,
  });

  final Widget child;
  final LpgSurfaceLevel level;
  final bool blur;
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

    final isCard = level == LpgSurfaceLevel.card;
    final look = LpgGlassLook.of(colors);
    final fill = DecoratedBox(
      decoration: BoxDecoration(
        color: blur && !isCard ? colors.sheetGlass : colors.cardGlass,
        borderRadius: shape,
        border: Border.fromBorderSide(colors.hairlineFor(level)),
      ),
      // The grain is over the fill and under the content.
      child: LpgGrainLayer(
        strength: blur && !isCard ? look.sheetGrain : look.surfaceGrain,
        child: content,
      ),
    );
    final panel = isCard
        ? ClipRRect(borderRadius: shape, child: fill)
        : LpgGlassPane(
            radius: shape,
            grain: 0,
            blurSigma: blur ? LpgGlassLook.blurSigma : null,
            child: fill,
          );
    return panel;
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
