import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'grain.dart';
import 'theme.dart';

/// The glass tokens of one theme: how the frosted look of *chrome* (the
/// navigation bar, sheets) is set. They are read from the theme's own colours
/// the same way [LpgBackdropLook] decides light from dark, so nothing here
/// selects, stores or switches a theme: a theme change is just new inputs.
///
/// The tint's opacity is not here: it is the contrast-derived one in
/// `LpgGlassLook` (bar and sheet), so text on glass stays at 4.5:1.
@immutable
class LpgGlassTokens {
  const LpgGlassTokens({
    required this.blurSigma,
    required this.grainOpacity,
    required this.grainBlend,
    required this.fallbackAlpha,
  });

  /// Backdrop blur, in logical pixels (CSS `blur(16px)` is the same sigma).
  final double blurSigma;

  /// Opacity of the unblurred grain laid over the glass (0.05 to 0.10).
  final double grainOpacity;
  final BlendMode grainBlend;

  /// Opacity of the solid fallback fill used when blur is off.
  final double fallbackAlpha;

  static const light = LpgGlassTokens(
    blurSigma: 16,
    grainOpacity: 0.065,
    grainBlend: BlendMode.softLight,
    fallbackAlpha: 0.92,
  );

  static const dark = LpgGlassTokens(
    blurSigma: 16,
    grainOpacity: 0.08,
    grainBlend: BlendMode.softLight,
    fallbackAlpha: 0.92,
  );

  static LpgGlassTokens of(LpgColors colors) =>
      colors.surfaceBase.computeLuminance() > 0.5 ? light : dark;

  /// The backdrop filter. Flutter's [BackdropFilter] takes an image filter
  /// only (there is no colour-matrix one), so the web's `saturate()` boost
  /// has no equivalent here: the tint carries the colour instead.
  ui.ImageFilter get filter => ui.ImageFilter.blur(
    sigmaX: blurSigma,
    sigmaY: blurSigma,
    tileMode: TileMode.clamp,
  );
}

/// Whether glass may blur at all. Starts on; an app (or a frame-time monitor)
/// can switch it off, and every glass surface then shows its solid fallback
/// tint with the same grain, with no re-mount. Never animated.
abstract final class LpgGlassPolicy {
  static final ValueNotifier<bool> blur = ValueNotifier(true);
}

/// Frosted chrome: the backdrop blurred by the compositor, then a tint, then
/// the paper's grain unblurred over both, then [child]. Used for bars and
/// sheets only, never for list items or cards.
///
/// One [BackdropFilter] per surface, clipped, in its own repaint boundary so
/// the blur is not redrawn when something else repaints. The grain is the
/// shared tile, decoded once ([LpgGrain]); nothing is allocated while drawing.
/// With blur off (policy, or high contrast) the same tint and grain are shown
/// at the fallback opacity.
class LpgGlassChrome extends StatelessWidget {
  const LpgGlassChrome({
    super.key,
    required this.fill,
    required this.alpha,
    required this.child,
    this.radius = BorderRadius.zero,
    this.border,
  });

  /// The opaque colour the tint is made from.
  final Color fill;

  /// The see-through opacity of the tint (contrast-derived).
  final double alpha;
  final BorderRadius radius;
  final BoxBorder? border;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    if (colors.isHighContrast) {
      return Stack(
        fit: StackFit.passthrough,
        children: [
          Positioned.fill(
            child: IgnorePointer(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: fill,
                  borderRadius: radius,
                  border: border,
                ),
              ),
            ),
          ),
          child,
        ],
      );
    }
    final tokens = LpgGlassTokens.of(colors);
    return ValueListenableBuilder<bool>(
      valueListenable: LpgGlassPolicy.blur,
      child: _Grain(tokens: tokens, child: child),
      builder: (context, blurOn, content) {
        final tint = fill.withValues(
          alpha: blurOn
              ? alpha
              : (alpha > tokens.fallbackAlpha ? alpha : tokens.fallbackAlpha),
        );
        // The tint is a sibling layer under the content, not an ancestor
        // decoration: Material widgets inside (ListTile, InkWell) paint on the
        // nearest Material and an ancestor DecoratedBox with a colour would
        // hide their ink.
        final surface = Stack(
          fit: StackFit.passthrough,
          children: [
            Positioned.fill(
              child: IgnorePointer(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: tint,
                    borderRadius: radius,
                    border: border,
                  ),
                ),
              ),
            ),
            content!,
          ],
        );
        return RepaintBoundary(
          child: ClipRRect(
            borderRadius: radius,
            child: blurOn
                ? BackdropFilter(filter: tokens.filter, child: surface)
                : surface,
          ),
        );
      },
    );
  }
}

/// Lays the grain over everything painted so far in the glass and under
/// [child] (see [LpgGlassChrome]).
class _Grain extends StatefulWidget {
  const _Grain({required this.tokens, required this.child});

  final LpgGlassTokens tokens;
  final Widget child;

  @override
  State<_Grain> createState() => _GrainState();
}

class _GrainState extends State<_Grain> {
  @override
  void initState() {
    super.initState();
    LpgGrain.ensureLoaded();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.passthrough,
      children: [
        Positioned.fill(
          child: ExcludeSemantics(
            child: IgnorePointer(
              child: ValueListenableBuilder<ui.Image?>(
                valueListenable: LpgGrain.image,
                builder: (context, tile, _) =>
                    CustomPaint(painter: _GrainPainter(tile, widget.tokens)),
              ),
            ),
          ),
        ),
        widget.child,
      ],
    );
  }
}

class _GrainPainter extends CustomPainter {
  _GrainPainter(this.tile, this.tokens);

  final ui.Image? tile;
  final LpgGlassTokens tokens;

  // Built once per painter (it only changes with the tile or the theme).
  late final Paint _paint = Paint()
    ..blendMode = tokens.grainBlend
    ..shader = ImageShader(
      tile!,
      TileMode.repeated,
      TileMode.repeated,
      Matrix4.diagonal3Values(LpgGrain.scale, LpgGrain.scale, 1).storage,
      filterQuality: FilterQuality.medium,
    )
    ..color = Color.fromRGBO(255, 255, 255, tokens.grainOpacity);

  @override
  void paint(Canvas canvas, Size size) {
    if (tile == null) return;
    canvas.drawRect(Offset.zero & size, _paint);
  }

  @override
  bool shouldRepaint(_GrainPainter old) =>
      old.tile != tile || old.tokens != tokens;
}
