import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';

/// The bordered, flat-elevation container every screen already reaches for
/// (`dashboard_screen.dart`'s balance card, `login_screen.dart`'s form
/// panel) — reuses `CardTheme`'s own colour/radius/border rather than
/// hand-building a `Container`/`BoxDecoration` per screen, and adds a tap
/// target and padding override for the cases that need one.
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
    final radius = BorderRadius.circular(LpgTokens.radiusLg * 1.0);
    final isHighContrast =
        Theme.of(context).brightness == Brightness.light &&
        colors.shadowLight == Colors.transparent;

    final content = Padding(padding: padding, child: child);

    return Container(
      decoration: BoxDecoration(
        color: colors.surfaceBase,
        borderRadius: radius,
        border: isHighContrast ? Border.all(color: colors.borderDefault) : null,
        boxShadow: isHighContrast ? null : colors.neumorphicShadows,
        gradient: isHighContrast
            ? null
            : LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  colors.surfaceBase,
                  colors.surfaceBase.withValues(alpha: 0.95),
                ],
              ),
      ),
      clipBehavior: Clip.antiAlias,
      child: onTap == null
          ? content
          : InkWell(onTap: onTap, borderRadius: radius, child: content),
    );
  }
}
