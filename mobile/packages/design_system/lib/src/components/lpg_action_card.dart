import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import '../tone.dart';
import 'lpg_card.dart';
import 'lpg_icon_box.dart';
import 'lpg_metric_tile.dart';

/// A card that says something is happening or needs the person, and takes
/// them to it: "On its way, Order ORD000060 is out for delivery, Track".
///
/// A tinted fill in [tone] with the same solid bar down the left edge as an
/// attention [LpgMetricTile], an icon, a title, a message, and a short action
/// label with a chevron. The whole card is the tap target and reads as one
/// button to a screen reader ("title. message").
class LpgActionCard extends StatelessWidget {
  const LpgActionCard({
    super.key,
    required this.title,
    required this.message,
    required this.icon,
    required this.onTap,
    this.actionLabel,
    this.tone = LpgTone.warning,
  });

  final String title;
  final String message;
  final IconData icon;
  final VoidCallback onTap;

  /// The verb on the right ("Track", "Review"); omitted, only the chevron.
  final String? actionLabel;
  final LpgTone tone;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return LpgCard(
      variant: LpgCardVariant.tonal,
      tone: tone,
      onTap: onTap,
      padding: EdgeInsets.zero,
      semanticLabel: '$title. $message',
      child: Stack(
        children: [
          Positioned.fill(
            right: null,
            child: ExcludeSemantics(
              child: SizedBox(
                width: LpgMetricTile.railWidth,
                child: ColoredBox(color: tone.foreground(colors)),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(LpgSpacing.md),
            child: Row(
              children: [
                LpgIconBox(icon: icon, tone: tone),
                const SizedBox(width: LpgSpacing.smd),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: text.titleSmall),
                      const SizedBox(height: LpgSpacing.xs / 2),
                      Text(message, style: text.bodySmall),
                    ],
                  ),
                ),
                if (actionLabel != null) ...[
                  const SizedBox(width: LpgSpacing.sm),
                  Text(
                    actionLabel!,
                    style: text.labelLarge?.copyWith(color: colors.textPrimary),
                  ),
                ],
                Icon(
                  LpgIcons.chevronRight,
                  size: LpgSizes.iconSm,
                  color: colors.textPrimary,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
