import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../grain.dart';
import '../theme.dart';
import '../tone.dart';

/// The page behind every screen: a sheet of paper with a few soft, blurred
/// colour washes and a fine grain.
///
/// It paints only the page. Cards and sheets are frosted glass laid over it
/// (see `LpgGlass`), so the washes show softly through them, and the washes and grain
/// are sized so secondary text on the page still clears 4.5:1 (see
/// [LpgBackdropLook]). In high contrast the page is plain.
///
/// The theme puts one under every route (see `lpgBackdropTransitions`), so
/// screens do not use this directly.
class LpgBackdrop extends StatefulWidget {
  const LpgBackdrop({super.key, required this.child});

  final Widget child;

  @override
  State<LpgBackdrop> createState() => _LpgBackdropState();
}

class _LpgBackdropState extends State<LpgBackdrop> {
  @override
  void initState() {
    super.initState();
    LpgGrain.ensureLoaded();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    if (colors.isHighContrast) {
      return ColoredBox(color: colors.canvas, child: widget.child);
    }
    final look = LpgBackdropLook.of(colors);
    return Stack(
      fit: StackFit.passthrough,
      children: [
        Positioned.fill(
          child: ExcludeSemantics(
            child: IgnorePointer(
              // Painted once into its own layer, so scrolling and page
              // transitions only move that picture.
              child: RepaintBoundary(
                child: ValueListenableBuilder<ui.Image?>(
                  valueListenable: LpgGrain.image,
                  builder: (context, grain, _) => CustomPaint(
                    painter: _BackdropPainter(look: look, grain: grain),
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

/// One blurred wash of colour.
@immutable
class LpgBackdropWash {
  const LpgBackdropWash({
    required this.color,
    required this.centre,
    required this.radius,
    this.sigma = 64,
  });

  /// An opaque colour: the page tinted towards a tone.
  final Color color;

  /// Where it sits, as a fraction of the page's width and height.
  final Offset centre;

  /// Its radius, as a fraction of the page's width.
  final double radius;

  /// How far its edge is blurred, in logical pixels. The big washes are
  /// blurred until no edge shows; the small orbs less, so a glass card laid
  /// over one has something to show through it.
  final double sigma;
}

/// What the page looks like in one theme, worked out from that theme's own
/// colours so it never has to be tuned per theme.
///
/// The page is the theme's base surface (white in the light theme), a few
/// washes of the tone colours, and grain. The strength of each is the
/// **largest that still keeps secondary text at [minTextContrast] or better**
/// on the worst pixel: a wash at its darkest or lightest, with a grain speck
/// on top. A theme with less room gets a fainter page (the light theme did,
/// until its secondary text was darkened to 7.6:1 on white) and it grows by
/// itself if a text colour is darkened.
@immutable
class LpgBackdropLook {
  const LpgBackdropLook({
    required this.base,
    required this.washes,
    required this.speck,
    required this.grainStrength,
  });

  /// The paper itself.
  final Color base;
  final List<LpgBackdropWash> washes;

  /// The colour of the grain speck that hurts contrast most (black on a light
  /// page, white on a dark one).
  final Color speck;

  /// How much of the grain shows, 0 to 1.
  final double grainStrength;

  /// Secondary text on the page, in the worst case, stays at or above this.
  /// AA asks for 4.5; the extra is for rounding.
  static const minTextContrast = 4.55;

  /// The washes stop this far above [minTextContrast], leaving the rest of
  /// the room for the grain so the page is never smooth-but-tinted only.
  static const _grainReserve = 0.45;

  /// What each wash and the grain would like to be if contrast allowed it.
  static const _washTarget = 0.34;
  static const _grainTarget = 0.07;

  static double contrast(Color a, Color b) {
    final la = a.computeLuminance();
    final lb = b.computeLuminance();
    final hi = la > lb ? la : lb;
    final lo = la > lb ? lb : la;
    return (hi + 0.05) / (lo + 0.05);
  }

  /// The largest strength up to [target] for which [ok] holds, by bisection
  /// (strength 0 is always allowed: it is the base itself).
  static double _largest(double target, bool Function(double) ok) {
    if (ok(target)) return target;
    var lo = 0.0;
    var hi = target;
    for (var i = 0; i < 14; i++) {
      final mid = (lo + hi) / 2;
      if (ok(mid)) {
        lo = mid;
      } else {
        hi = mid;
      }
    }
    return lo;
  }

  static LpgBackdropLook of(LpgColors colors) {
    final base = colors.surfaceBase;
    final text = colors.textSecondary;

    LpgBackdropWash wash(
      LpgTone tone,
      Offset centre,
      double radius, [
      double sigma = 64,
    ]) {
      final hue = tone.foreground(colors);
      final strength = _largest(
        _washTarget,
        (s) =>
            contrast(text, colors.tint(hue, s, over: base)) >=
            minTextContrast + _grainReserve,
      );
      return LpgBackdropWash(
        color: colors.tint(hue, strength, over: base),
        centre: centre,
        radius: radius,
        sigma: sigma,
      );
    }

    final washes = [
      wash(LpgTone.primary, const Offset(0.95, 0.06), 0.62),
      wash(LpgTone.accent, const Offset(0.02, 0.46), 0.56),
      wash(LpgTone.info, const Offset(0.9, 0.98), 0.66),
      // Two smaller, crisper orbs in the middle of the page, where cards sit:
      // glass over a flat page looks like a plain card, over these it shows.
      wash(LpgTone.accent, const Offset(0.78, 0.40), 0.26, 30),
      wash(LpgTone.info, const Offset(0.16, 0.74), 0.30, 34),
    ];

    // The grain lands on the page or on a wash; take the one text reads worst
    // on, then the speck that hurts most there.
    final speck = base.computeLuminance() > 0.5
        ? const Color(0xFF000000)
        : const Color(0xFFFFFFFF);
    final worstBase = washes
        .map((w) => w.color)
        .followedBy([base])
        .reduce((a, b) => contrast(text, a) < contrast(text, b) ? a : b);
    final grain = _largest(
      _grainTarget,
      (s) =>
          contrast(text, colors.tint(speck, s, over: worstBase)) >=
          minTextContrast,
    );

    return LpgBackdropLook(
      base: base,
      washes: washes,
      speck: speck,
      grainStrength: grain,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is LpgBackdropLook &&
      other.base == base &&
      other.speck == speck &&
      other.grainStrength == grainStrength &&
      _sameWashes(other.washes);

  bool _sameWashes(List<LpgBackdropWash> other) {
    if (other.length != washes.length) return false;
    for (var i = 0; i < washes.length; i++) {
      if (other[i].color != washes[i].color) return false;
    }
    return true;
  }

  @override
  int get hashCode => Object.hash(base, speck, grainStrength, washes.length);
}

class _BackdropPainter extends CustomPainter {
  _BackdropPainter({required this.look, required this.grain});

  final LpgBackdropLook look;
  final ui.Image? grain;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..color = look.base);

    canvas.save();
    canvas.clipRect(rect);
    for (final wash in look.washes) {
      canvas.drawCircle(
        Offset(wash.centre.dx * size.width, wash.centre.dy * size.height),
        wash.radius * size.width,
        Paint()
          ..color = wash.color
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, wash.sigma),
      );
    }
    canvas.restore();

    final tile = grain;
    if (tile == null) return;
    LpgGrain.paint(canvas, rect, tile, look.grainStrength);
  }

  @override
  bool shouldRepaint(_BackdropPainter old) =>
      old.look != look || old.grain != grain;
}

/// Wraps [inner] so the page is drawn under the screen it shows. Screens'
/// scaffolds are transparent, so without this the page would be empty, and
/// doing it per route (rather than once behind the navigator) keeps a sliding
/// page opaque while it moves.
class LpgBackdropTransitions extends PageTransitionsBuilder {
  const LpgBackdropTransitions(this.inner);

  final PageTransitionsBuilder inner;

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) => inner.buildTransitions(
    route,
    context,
    animation,
    secondaryAnimation,
    LpgBackdrop(child: child),
  );
}
