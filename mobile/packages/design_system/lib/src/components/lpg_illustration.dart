import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../motion.dart';
import '../theme.dart';
import '../tone.dart';

/// The picture behind a stat card: what the number is about, drawn in the
/// card's own tone so the figure on top stays the loudest thing.
enum LpgIllustration {
  /// Notes stacked with a coin: money expected.
  banknotes,

  /// A note with a tick: money received.
  cashReceived,

  /// A note with a bite out of it and a down arrow: money missing.
  shortfall,

  /// A stack of coins with an up arrow: more than expected.
  excess,
}

/// How strongly each layer of a picture tints the card, from the faintest
/// large shapes to the small accents. The strongest is what text can end up
/// over, and a test holds every tone to 4.5:1 against it.
abstract final class LpgIllustrationTint {
  static const soft = 0.10;
  static const mid = 0.17;
  static const strong = 0.26;
}

/// A flat, solid-colour illustration that settles into place once and then
/// breathes a few times before resting, so a screen of them is lively when it
/// opens and still afterwards.
///
/// Decorative: excluded from semantics and touches. Nothing here uses
/// transparency, so contrast does not depend on what is behind it. Under the
/// platform's reduce-motion setting it is drawn finished and never moves; in
/// high contrast it is not drawn at all, because fills stay plain there.
class LpgIllustrationArt extends StatefulWidget {
  const LpgIllustrationArt({
    super.key,
    required this.illustration,
    this.tone = LpgTone.primary,
    this.size = defaultSize,
  });

  final LpgIllustration illustration;
  final LpgTone tone;
  final double size;

  static const double defaultSize = 116;

  @override
  State<LpgIllustrationArt> createState() => _LpgIllustrationArtState();
}

class _LpgIllustrationArtState extends State<LpgIllustrationArt>
    with TickerProviderStateMixin {
  static const _settle = Duration(milliseconds: 800);
  static const _breath = Duration(milliseconds: 2600);

  late final AnimationController _entry = AnimationController(
    vsync: this,
    duration: _settle,
  );
  late final AnimationController _breathing = AnimationController(
    vsync: this,
    duration: _breath,
  );
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) {
      _entry.value = 1;
      return;
    }
    _entry.forward().whenComplete(() {
      if (!mounted) return;
      _breathing.repeat(count: LpgMotion.pulseRepeats);
    });
  }

  @override
  void dispose() {
    _entry.dispose();
    _breathing.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    if (colors.isHighContrast) return const SizedBox.shrink();
    final palette = _Palette(
      soft: colors.tint(
        widget.tone.foreground(colors),
        LpgIllustrationTint.soft,
      ),
      mid: colors.tint(widget.tone.foreground(colors), LpgIllustrationTint.mid),
      strong: colors.tint(
        widget.tone.foreground(colors),
        LpgIllustrationTint.strong,
      ),
      ground: colors.card,
    );
    return ExcludeSemantics(
      child: IgnorePointer(
        child: RepaintBoundary(
          child: CustomPaint(
            size: Size.square(widget.size),
            painter: _ArtPainter(
              illustration: widget.illustration,
              palette: palette,
              entry: _entry,
              breathing: _breathing,
            ),
          ),
        ),
      ),
    );
  }
}

class _Palette {
  const _Palette({
    required this.soft,
    required this.mid,
    required this.strong,
    required this.ground,
  });

  final Color soft;
  final Color mid;
  final Color strong;

  /// The card colour, for marks cut out of a shape (a tick, a bite).
  final Color ground;

  @override
  bool operator ==(Object other) =>
      other is _Palette &&
      other.soft == soft &&
      other.mid == mid &&
      other.strong == strong &&
      other.ground == ground;

  @override
  int get hashCode => Object.hash(soft, mid, strong, ground);
}

class _ArtPainter extends CustomPainter {
  _ArtPainter({
    required this.illustration,
    required this.palette,
    required this.entry,
    required this.breathing,
  }) : super(repaint: Listenable.merge([entry, breathing]));

  final LpgIllustration illustration;
  final _Palette palette;
  final Animation<double> entry;
  final Animation<double> breathing;

  /// Pictures are drawn in a 100 x 100 box and scaled to fit.
  static const _box = 100.0;

  /// One part's own progress inside the whole entrance.
  static double _part(double t, double from, double to, [Curve? curve]) =>
      Interval(from, to, curve: curve ?? Curves.easeOutCubic).transform(t);

  @override
  void paint(Canvas canvas, Size size) {
    final e = entry.value;
    // One slow in-and-out, ending exactly where it began.
    final b = math.sin(breathing.value * 2 * math.pi);
    canvas.save();
    canvas.scale(size.width / _box);
    switch (illustration) {
      case LpgIllustration.banknotes:
        _banknotes(canvas, e, b);
      case LpgIllustration.cashReceived:
        _cashReceived(canvas, e, b);
      case LpgIllustration.shortfall:
        _shortfall(canvas, e, b);
      case LpgIllustration.excess:
        _excess(canvas, e, b);
    }
    canvas.restore();
  }

  Paint _fill(Color c) => Paint()..color = c;

  Paint _line(Color c, double width) => Paint()
    ..color = c
    ..style = PaintingStyle.stroke
    ..strokeWidth = width
    ..strokeCap = StrokeCap.round
    ..strokeJoin = StrokeJoin.round;

  /// A banknote centred on the origin.
  void _note(Canvas canvas, Size s, Color body, Color detail) {
    final rect = Rect.fromCenter(
      center: Offset.zero,
      width: s.width,
      height: s.height,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(6)),
      _fill(body),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect.deflate(4.5), const Radius.circular(3.5)),
      _line(detail, 1.4),
    );
    canvas.drawCircle(Offset.zero, s.height * 0.22, _line(detail, 1.8));
    canvas.drawCircle(Offset(-s.width * 0.31, 0), 2.2, _fill(detail));
    canvas.drawCircle(Offset(s.width * 0.31, 0), 2.2, _fill(detail));
  }

  void _banknotes(Canvas canvas, double e, double b) {
    final back = _part(e, 0.0, 0.7);
    final front = _part(e, 0.2, 0.95);
    final coin = _part(e, 0.5, 1.0, Curves.easeOutBack);

    canvas.save();
    canvas.translate(54, 46 - 16 * (1 - back) - b * 1.6);
    canvas.rotate(8 * math.pi / 180);
    _note(canvas, const Size(70, 42), palette.soft, palette.mid);
    canvas.restore();

    canvas.save();
    canvas.translate(60 + 30 * (1 - front), 68 + b * 1.6);
    canvas.rotate(-6 * math.pi / 180);
    _note(canvas, const Size(70, 42), palette.mid, palette.strong);
    canvas.restore();

    canvas.save();
    canvas.translate(26, 84 - b * 1.2);
    canvas.scale(coin.clamp(0.0, 1.2));
    canvas.drawCircle(Offset.zero, 11, _fill(palette.strong));
    canvas.drawCircle(Offset.zero, 6.5, _line(palette.ground, 1.8));
    canvas.restore();
  }

  void _cashReceived(Canvas canvas, double e, double b) {
    final note = _part(e, 0.0, 0.7);
    final badge = _part(e, 0.4, 0.9, Curves.easeOutBack);
    final tick = _part(e, 0.65, 1.0);

    canvas.save();
    canvas.translate(52 + 28 * (1 - note), 52 - b * 1.6);
    canvas.rotate(-8 * math.pi / 180);
    _note(canvas, const Size(72, 44), palette.mid, palette.strong);
    canvas.restore();

    canvas.save();
    canvas.translate(74, 74 + b * 1.4);
    canvas.scale(badge.clamp(0.0, 1.2));
    canvas.drawCircle(Offset.zero, 17, _fill(palette.strong));
    canvas.drawCircle(Offset.zero, 17, _line(palette.ground, 3));
    final path = Path()
      ..moveTo(-7, 0.5)
      ..lineTo(-2, 5.5)
      ..lineTo(8, -5);
    final metric = path.computeMetrics().first;
    canvas.drawPath(
      metric.extractPath(0, metric.length * tick),
      _line(palette.ground, 3.4),
    );
    canvas.restore();
  }

  void _shortfall(Canvas canvas, double e, double b) {
    final note = _part(e, 0.0, 0.7);
    final arrow = _part(e, 0.35, 1.0, Curves.bounceOut);

    canvas.save();
    canvas.translate(54, 50 + 18 * (1 - note) - b * 1.4);
    canvas.rotate(6 * math.pi / 180);
    _note(canvas, const Size(72, 44), palette.mid, palette.strong);
    // The missing piece: a bite cut out of the corner in the card's colour.
    canvas.drawCircle(const Offset(34, -20), 13, _fill(palette.ground));
    canvas.restore();

    canvas.save();
    canvas.translate(30, 76 - 18 * (1 - arrow) + b * 1.4);
    canvas.drawCircle(Offset.zero, 17, _fill(palette.strong));
    canvas.drawCircle(Offset.zero, 17, _line(palette.ground, 3));
    final line = _line(palette.ground, 3.4);
    canvas.drawLine(const Offset(0, -7), const Offset(0, 7), line);
    canvas.drawLine(const Offset(0, 7), const Offset(-5.5, 1.5), line);
    canvas.drawLine(const Offset(0, 7), const Offset(5.5, 1.5), line);
    canvas.restore();
  }

  /// A coin lying flat, centred on the origin.
  void _coin(Canvas canvas, Color body, Color edge) {
    final rect = Rect.fromCenter(center: Offset.zero, width: 50, height: 14);
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(7)),
      _fill(body),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect.deflate(3), const Radius.circular(4)),
      _line(edge, 1.3),
    );
  }

  void _excess(Canvas canvas, double e, double b) {
    final colours = [palette.soft, palette.mid, palette.strong];
    for (var i = 0; i < 3; i++) {
      final drop = _part(e, i * 0.2, i * 0.2 + 0.55, Curves.bounceOut);
      canvas.save();
      canvas.translate(52, 82 - i * 15.0 - 26 * (1 - drop));
      _coin(canvas, colours[i], i == 2 ? palette.ground : palette.strong);
      canvas.restore();
    }

    final arrow = _part(e, 0.5, 1.0, Curves.easeOutBack);
    canvas.save();
    canvas.translate(78, 30 - b * 2.2);
    canvas.scale(arrow.clamp(0.0, 1.2));
    canvas.drawCircle(Offset.zero, 16, _fill(palette.strong));
    canvas.drawCircle(Offset.zero, 16, _line(palette.ground, 3));
    final line = _line(palette.ground, 3.4);
    canvas.drawLine(const Offset(0, 7), const Offset(0, -7), line);
    canvas.drawLine(const Offset(0, -7), const Offset(-5.5, -1.5), line);
    canvas.drawLine(const Offset(0, -7), const Offset(5.5, -1.5), line);
    canvas.restore();
  }

  @override
  bool shouldRepaint(_ArtPainter old) =>
      old.illustration != illustration || old.palette != palette;
}
