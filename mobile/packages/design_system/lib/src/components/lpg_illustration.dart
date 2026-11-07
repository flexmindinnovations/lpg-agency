import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

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

/// A flat, solid-colour illustration, still: it is drawn once and never moves,
/// so a screen of tiles costs nothing while it scrolls.
///
/// Decorative: excluded from semantics and touches. It is drawn at
/// [opacity] so it sits quietly behind the tile's text; it is only ever
/// fainter than the solid art, so it cannot cost the text any contrast. In
/// high contrast it is not drawn at all, because fills stay plain there.
class LpgIllustrationArt extends StatelessWidget {
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

  /// How strongly the art shows over the card, 0 to 1.
  static const double opacity = 0.4;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    if (colors.isHighContrast) return const SizedBox.shrink();
    final base = tone.foreground(colors);
    return ExcludeSemantics(
      child: IgnorePointer(
        // Drawn once into its own layer, so a scroll only moves that picture.
        child: RepaintBoundary(
          child: Opacity(
            opacity: opacity,
            child: SvgPicture.asset(
              illustration.assetPath,
              package: 'design_system',
              width: size,
              height: size,
              colorMapper: _ToneColors(
                soft: colors.tint(base, LpgIllustrationTint.soft),
                mid: colors.tint(base, LpgIllustrationTint.mid),
                strong: colors.tint(base, LpgIllustrationTint.strong),
                ground: colors.card,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
