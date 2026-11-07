import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// A brand-gradient panel for the one headline fact on a screen: the
/// customer's cylinder balance, the driver's progress through today's
/// route, the sign-in header.
///
/// Children should colour themselves with `context.lpgColors.onHero`. A
/// faint oversized [watermark] icon sits in the corner for texture; it is
/// decorative and excluded from semantics. Set [keepClearOfWatermark] when
/// the child has long text lines, so they wrap before reaching the icon.
class LpgHeroCard extends StatelessWidget {
  const LpgHeroCard({
    super.key,
    required this.child,
    this.watermark,
    this.padding = const EdgeInsets.all(LpgSpacing.lg),
    this.keepClearOfWatermark = false,
    this.onTap,
  });

  final Widget child;
  final IconData? watermark;
  final EdgeInsetsGeometry padding;

  /// Keeps the child out of the watermark's corner by reserving that width on
  /// the right, so a long line wraps instead of running over the icon.
  final bool keepClearOfWatermark;
  final VoidCallback? onTap;

  static const double _watermarkSize = LpgSizes.avatarLg * 2;
  static const double _watermarkOffset = LpgSpacing.lg;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final radius = BorderRadius.circular(LpgRadius.xxl);
    final contentPadding = padding.resolve(Directionality.of(context));
    // How far the icon reaches into the content box, past the card padding.
    final watermarkReach = keepClearOfWatermark && watermark != null
        ? (_watermarkSize - _watermarkOffset - contentPadding.right).clamp(
            0.0,
            double.infinity,
          )
        : 0.0;

    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: radius,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: colors.heroGradient,
        ),
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
                  right: -_watermarkOffset,
                  bottom: -LpgSpacing.xl,
                  child: ExcludeSemantics(
                    child: Icon(
                      watermark,
                      size: _watermarkSize,
                      color: colors.heroSubtle,
                    ),
                  ),
                ),
              Padding(
                padding: padding,
                child: DefaultTextStyle.merge(
                  style: TextStyle(color: colors.onHero),
                  child: IconTheme.merge(
                    data: IconThemeData(color: colors.onHero),
                    child: watermarkReach == 0
                        ? child
                        : Padding(
                            padding: EdgeInsets.only(right: watermarkReach),
                            child: child,
                          ),
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
