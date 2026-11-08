import 'package:flutter/material.dart';

import '../glass.dart';
import '../layout.dart';
import '../motion.dart';
import '../theme.dart';
import '../tone.dart';

/// How an [LpgCard] separates itself from the canvas.
enum LpgCardVariant {
  /// Card fill and hairline border; no shadow. The default.
  outlined,

  /// A tinted fill in the card's [LpgCard.tone], no border — for
  /// callouts and selected states.
  tonal,

  /// The card fill with no border, for screens where the hairline looks
  /// heavy (dark mode). High contrast still draws its border.
  plain,
}

/// The container every screen groups content in.
///
/// A real `Material`/`InkWell` underneath, so a tappable card gets a genuine
/// ripple, wrapped in [LpgPressable] for the same spring "give" buttons
/// have. High contrast uses a 2px border.
class LpgCard extends StatelessWidget {
  const LpgCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(LpgSpacing.mdl),
    this.onTap,
    this.variant = LpgCardVariant.outlined,
    this.tone = LpgTone.primary,
    this.semanticLabel,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final LpgCardVariant variant;

  /// Only used by [LpgCardVariant.tonal].
  final LpgTone tone;

  /// Announced instead of the card's children when it is tappable, so a
  /// screen reader hears "Order 1042, delivered" rather than every text
  /// fragment inside.
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final hc = colors.isHighContrast;

    // Elevated and outlined cards are slightly see-through, so the page shows
    // softly through them; a tonal card is an opaque tint of its tone.
    final fill = variant == LpgCardVariant.tonal
        ? tone.container(colors)
        : colors.cardGlass;
    final BorderSide side;
    if (hc) {
      side = BorderSide(color: colors.borderStrong, width: 2);
    } else if (variant == LpgCardVariant.tonal ||
        variant == LpgCardVariant.plain) {
      side = BorderSide.none;
    } else {
      side = BorderSide(color: colors.outline);
    }
    final shape = RoundedRectangleBorder(
      borderRadius: LpgRadius.cardRadius,
      side: side,
    );

    final content = Padding(padding: padding, child: child);

    final surface = Material(
      color: fill,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: onTap == null
          ? content
          : InkWell(onTap: onTap, customBorder: shape, child: content),
    );

    Widget card = surface;

    if (onTap != null) {
      card = LpgPressable(enabled: true, child: card);
      if (semanticLabel != null) {
        card = Semantics(
          button: true,
          label: semanticLabel,
          excludeSemantics: true,
          onTap: onTap,
          child: card,
        );
      }
    }
    return card;
  }
}
