import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import '../tone.dart';
import 'lpg_card.dart';
import 'lpg_icon_box.dart';

/// A big, tappable number for a dashboard: tinted icon, the figure in heavy
/// tabular numerals so columns of tiles line up, a label, and an optional
/// caption in the tile's tone ("4 to review").
///
/// When [attention] is set, a solid bar in the tone runs down the left edge
/// and the caption takes the tone, so a tile that needs the owner stands out
/// without relying on colour alone: the caption says why. Otherwise the
/// caption stays in the secondary text colour, so it never reads as a link.
class LpgMetricTile extends StatelessWidget {
  const LpgMetricTile({
    super.key,
    required this.label,
    required this.value,
    required this.icon,
    this.caption,
    this.tone = LpgTone.primary,
    this.onTap,
    this.attention = false,
  });

  final String label;
  final String value;
  final IconData icon;

  /// A smaller line under the label ("3 invoices").
  final String? caption;
  final LpgTone tone;

  /// Makes the tile tappable and shows a chevron.
  final VoidCallback? onTap;
  final bool attention;

  /// Width of the attention bar.
  static const double railWidth = 4;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final tappable = onTap != null;
    final railColor = tone.foreground(colors);
    final figure = (text.headlineMedium ?? const TextStyle()).copyWith(
      fontWeight: FontWeight.w800,
      fontFeatures: const [FontFeature.tabularFigures()],
    );

    return Semantics(
      button: tappable,
      label: ['$label: $value', if (caption != null) caption!].join(', '),
      excludeSemantics: true,
      child: LpgCard(
        onTap: onTap,
        padding: EdgeInsets.zero,
        child: Stack(
          children: [
            if (attention)
              Positioned.fill(
                right: null,
                child: ExcludeSemantics(
                  child: SizedBox(
                    width: railWidth,
                    child: ColoredBox(color: railColor),
                  ),
                ),
              ),
            Padding(
              // The bar sits in the left padding, so tiles line up whether or
              // not they carry one.
              padding: const EdgeInsets.all(LpgSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      LpgIconBox(icon: icon, tone: tone, size: 36),
                      const Spacer(),
                      if (tappable)
                        Icon(
                          LpgIcons.chevronRight,
                          size: LpgSizes.iconSm,
                          color: colors.textSecondary,
                        ),
                    ],
                  ),
                  const SizedBox(height: LpgSpacing.smd),
                  Text(
                    value,
                    style: figure,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    label,
                    style: text.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (caption != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        caption!,
                        style: text.labelMedium?.copyWith(
                          color: attention ? railColor : colors.textSecondary,
                          fontWeight: FontWeight.w700,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
