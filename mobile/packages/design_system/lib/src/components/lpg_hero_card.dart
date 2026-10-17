import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// A brand-gradient panel for the one headline fact on a screen: the
/// customer's cylinder balance, the driver's progress through today's
/// route, the sign-in header.
///
/// Children should colour themselves with `context.lpgColors.onHero`. A
/// faint oversized [watermark] icon sits in the corner for texture; it is
/// decorative and excluded from semantics.
class LpgHeroCard extends StatelessWidget {
  const LpgHeroCard({
    super.key,
    required this.child,
    this.watermark,
    this.padding = const EdgeInsets.all(LpgSpacing.lg),
    this.onTap,
  });

  final Widget child;
  final IconData? watermark;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final radius = BorderRadius.circular(LpgRadius.xxl);

    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: radius,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: colors.heroGradient,
        ),
        boxShadow: colors.isHighContrast ? null : colors.floatingShadow,
      ),
      child: Material(
        type: MaterialType.transparency,
        borderRadius: radius,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Stack(
            children: [
              if (watermark != null)
                Positioned(
                  right: -LpgSpacing.lg,
                  bottom: -LpgSpacing.xl,
                  child: ExcludeSemantics(
                    child: Icon(
                      watermark,
                      size: LpgSizes.avatarLg * 2,
                      color: colors.onHero.withValues(alpha: 0.08),
                    ),
                  ),
                ),
              Padding(
                padding: padding,
                child: DefaultTextStyle.merge(
                  style: TextStyle(color: colors.onHero),
                  child: IconTheme.merge(
                    data: IconThemeData(color: colors.onHero),
                    child: child,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
