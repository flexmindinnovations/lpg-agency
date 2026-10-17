import 'package:flutter/material.dart';

import '../layout.dart';
import '../motion.dart';
import '../theme.dart';
import '../tone.dart';

/// How an [LpgCard] separates itself from the canvas.
enum LpgCardVariant {
  /// Card fill, hairline border and a soft resting shadow. The default.
  elevated,

  /// Card fill and border, no shadow — for cards nested inside other cards
  /// or dense lists where shadows would stack up.
  outlined,

  /// A tinted fill in the card's [LpgCard.tone], no border or shadow — for
  /// callouts and selected states.
  tonal,
}

/// The container every screen groups content in.
///
/// A real `Material`/`InkWell` underneath, so a tappable card gets a genuine
/// ripple, wrapped in [LpgPressable] for the same spring "give" buttons
/// have. High contrast swaps shadow for a 2px border, since shadow-based
/// elevation is often imperceptible to low-vision users.
class LpgCard extends StatelessWidget {
  const LpgCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(LpgSpacing.mdl),
    this.onTap,
    this.variant = LpgCardVariant.elevated,
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

    final fill = variant == LpgCardVariant.tonal
        ? tone.container(colors)
        : colors.card;
    final BorderSide side;
    if (hc) {
      side = BorderSide(color: colors.borderStrong, width: 2);
    } else if (variant == LpgCardVariant.tonal) {
      side = BorderSide.none;
    } else {
      side = BorderSide(color: colors.borderDefault);
    }
    final shape = RoundedRectangleBorder(
      borderRadius: LpgRadius.cardRadius,
      side: side,
    );

    final content = Padding(padding: padding, child: child);

    Widget card = DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: LpgRadius.cardRadius,
        boxShadow: variant == LpgCardVariant.elevated && !hc
            ? colors.cardShadow
            : null,
      ),
      child: Material(
        color: fill,
        shape: shape,
        clipBehavior: Clip.antiAlias,
        child: onTap == null
            ? content
            : InkWell(onTap: onTap, customBorder: shape, child: content),
      ),
    );

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
