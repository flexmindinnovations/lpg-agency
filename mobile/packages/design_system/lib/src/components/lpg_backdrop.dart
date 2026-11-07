import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../grain.dart';
import '../theme.dart';

/// The page behind every screen: a sheet of paper with a fine grain, the same
/// grain the navigation bar carries.
///
/// It paints only the page, once, into its own layer. Cards are a see-through
/// fill over it, so the grain shows softly through them; the grain is sized so
/// secondary text on the page still clears 4.5:1 (see [LpgBackdropLook]). There
/// is nothing blurred on the page: blurred washes and a backdrop blur on every
/// card were what made scrolling drop frames. In high contrast the page is
/// plain.
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

/// What the page looks like in one theme, worked out from that theme's own
/// colours so it never has to be tuned per theme.
///
/// The page is the theme's base surface (white in the light theme) and grain.
/// The grain is the **largest that still keeps secondary text at
/// [minTextContrast] or better** on the worst pixel: the base with a grain
/// speck on top. A theme with less room gets a finer grain and it grows by
/// itself if a text colour is darkened.
@immutable
class LpgBackdropLook {
  const LpgBackdropLook({
    required this.base,
    required this.speck,
    required this.grainStrength,
  });

  /// The paper itself.
  final Color base;

  /// The colour of the grain speck that hurts contrast most (black on a light
  /// page, white on a dark one).
  final Color speck;

  /// How much of the grain shows, 0 to 1.
  final double grainStrength;

  /// Secondary text on the page, in the worst case, stays at or above this.
  /// AA asks for 4.5; the extra is for rounding.
  static const minTextContrast = 4.55;

  /// What the grain would like to be if contrast allowed it: as strong as
  /// the grain on the navigation bar.
  static const _grainTarget = 0.2;

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

    // The speck that hurts most: black on a light page, white on a dark one.
    final speck = base.computeLuminance() > 0.5
        ? const Color(0xFF000000)
        : const Color(0xFFFFFFFF);
    final grain = _largest(
      _grainTarget,
      (s) => contrast(text, colors.tint(speck, s, over: base)) >=
          minTextContrast,
    );

    return LpgBackdropLook(base: base, speck: speck, grainStrength: grain);
  }

  @override
  bool operator ==(Object other) =>
      other is LpgBackdropLook &&
      other.base == base &&
      other.speck == speck &&
      other.grainStrength == grainStrength;

  @override
  int get hashCode => Object.hash(base, speck, grainStrength);
}

class _BackdropPainter extends CustomPainter {
  _BackdropPainter({required this.look, required this.grain});

  final LpgBackdropLook look;
  final ui.Image? grain;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..color = look.base);

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
