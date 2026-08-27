import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';

/// The flat, tonal-surface container every screen already reaches for
/// (`dashboard_screen.dart`'s balance card, `login_screen.dart`'s form
/// panel). A "squircle" (continuous-corner) shape rather than a plain
/// rounded rectangle — Material 3 Expressive treats shape as part of a
/// component's identity, not just a corner radius — and a real `Material`/
/// `InkWell` underneath instead of a decorated `Container`, so a tappable
/// card gets a genuine M3 ripple instead of nothing.
class LpgCard extends StatelessWidget {
  const LpgCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(LpgTokens.spacingLg * 1.0),
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final shape = ContinuousRectangleBorder(
      borderRadius: BorderRadius.circular(LpgTokens.radiusLg * 1.5),
      side: colors.isHighContrast
          ? BorderSide(color: colors.borderStrong, width: 2)
          : BorderSide.none,
    );

    final content = Padding(padding: padding, child: child);

    return Material(
      color: colors.surfaceRaised,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      elevation: 0,
      child: onTap == null
          ? content
          : InkWell(onTap: onTap, customBorder: shape, child: content),
    );
  }
}
