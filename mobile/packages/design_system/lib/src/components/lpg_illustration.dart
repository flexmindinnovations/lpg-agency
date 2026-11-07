import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../motion.dart';
import '../theme.dart';
import '../tone.dart';

/// The pictures that can sit behind a stat card. Each is an SVG file in
/// `assets/illustrations/`, shared by every app; this enum is the only place
/// that names them.
enum LpgIllustration {
  /// Notes stacked with a coin: money expected.
  banknotes('banknotes'),

  /// A note with a tick: money received.
  cashReceived('cash_received'),

  /// A note with a bite out of it and a down arrow: money missing.
  shortfall('shortfall'),

  /// A stack of coins with an up arrow: more than expected.
  excess('excess'),

  /// A clipboard with a clock: orders waiting for someone.
  pendingOrder('pending_order'),

  /// Two LPG cylinders: stock, or a load ready to go.
  cylinders('cylinders'),

  /// A dashed route to a map pin: on the road.
  route('route'),

  /// A parcel with a cross: a delivery that did not happen.
  failed('failed'),

  /// A person in a cap at a steering wheel: a driver.
  driver('driver'),

  /// A delivery van: a vehicle.
  van('van'),

  /// A wallet with a note sticking out: cash someone is holding.
  wallet('wallet'),

  /// An invoice with a rupee mark: money owed.
  invoice('invoice'),

  /// An invoice with a clock: money owed and late.
  overdue('overdue'),

  /// An invoice with a tick: settled.
  paid('paid'),

  /// Two speech bubbles, one with an exclamation mark: complaints.
  complaint('complaint'),

  /// A godown with a roller door: stock held.
  warehouse('warehouse');

  const LpgIllustration(this.fileName);

  /// The SVG's name in `assets/illustrations/`, without the extension.
  final String fileName;

  /// The asset path inside this package.
  String get assetPath => 'assets/illustrations/$fileName.svg';
}

/// The four colours an illustration SVG may use. The file is drawn in these
/// placeholder greys and [LpgIllustrationArt] swaps each for a tint of the
/// tile's tone when it is drawn, so the artwork carries no theme colour of its
/// own and a new tone or theme needs no new files.
abstract final class LpgIllustrationPalette {
  /// The largest, faintest shapes.
  static const soft = Color(0xFFD9D9D9);

  /// The main body of a picture.
  static const mid = Color(0xFFB3B3B3);

  /// Small accents: badges, valves, wheels.
  static const strong = Color(0xFF808080);

  /// Marks cut out of a shape, drawn in the card's own colour.
  static const ground = Color(0xFFFFFFFF);

  static const all = [soft, mid, strong, ground];
}

/// How strongly each layer of a picture tints the card, from the faintest
/// large shapes to the small accents. The strongest is what text can end up
/// over, and a test holds every tone to 4.5:1 against it.
abstract final class LpgIllustrationTint {
  static const soft = 0.10;
  static const mid = 0.17;
  static const strong = 0.26;
}

/// Swaps the SVG's four placeholder colours for the tile's tints. Compared by
/// value so the loader (and so the parsed picture) is cached across rebuilds.
class _ToneColors extends ColorMapper {
  const _ToneColors({
    required this.soft,
    required this.mid,
    required this.strong,
    required this.ground,
  });

  final Color soft;
  final Color mid;
  final Color strong;
  final Color ground;

  @override
  Color substitute(
    String? id,
    String elementName,
    String attributeName,
    Color color,
  ) {
    if (color == LpgIllustrationPalette.soft) return soft;
    if (color == LpgIllustrationPalette.mid) return mid;
    if (color == LpgIllustrationPalette.strong) return strong;
    if (color == LpgIllustrationPalette.ground) return ground;
    return color;
  }

  @override
  bool operator ==(Object other) =>
      other is _ToneColors &&
      other.soft == soft &&
      other.mid == mid &&
      other.strong == strong &&
      other.ground == ground;

  @override
  int get hashCode => Object.hash(soft, mid, strong, ground);
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
  late final Animation<double> _arrival = CurvedAnimation(
    parent: _entry,
    curve: Curves.easeOutBack,
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
    final base = widget.tone.foreground(colors);
    // Drawn once into its own layer; the motion below only moves that layer.
    final picture = RepaintBoundary(
      child: SvgPicture.asset(
        widget.illustration.assetPath,
        package: 'design_system',
        width: widget.size,
        height: widget.size,
        colorMapper: _ToneColors(
          soft: colors.tint(base, LpgIllustrationTint.soft),
          mid: colors.tint(base, LpgIllustrationTint.mid),
          strong: colors.tint(base, LpgIllustrationTint.strong),
          ground: colors.card,
        ),
      ),
    );
    return ExcludeSemantics(
      child: IgnorePointer(
        child: SizedBox.square(
          dimension: widget.size,
          child: AnimatedBuilder(
            animation: Listenable.merge([_arrival, _breathing]),
            child: picture,
            builder: (context, child) {
              final e = _arrival.value;
              // One slow in-and-out, ending exactly where it began.
              final b = math.sin(_breathing.value * 2 * math.pi);
              return Transform.translate(
                offset: Offset(
                  widget.size * 0.18 * (1 - e),
                  widget.size * 0.14 * (1 - e) + b * 2,
                ),
                child: Transform.scale(
                  scale: (0.86 + 0.14 * e) * (1 + 0.012 * b),
                  alignment: Alignment.bottomRight,
                  child: child,
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
