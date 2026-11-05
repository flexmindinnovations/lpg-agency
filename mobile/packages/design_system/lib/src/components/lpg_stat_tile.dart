import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import '../tone.dart';
import 'lpg_card.dart';
import 'lpg_icon_box.dart';

/// One metric number with its label, optional trend indicator and icon:
/// "₹1,240.00 Collected (+12.4%)", "14 Stops Pending".
class LpgStatTile extends StatelessWidget {
  const LpgStatTile({
    super.key,
    required this.label,
    required this.value,
    this.subtitle,
    this.icon,
    this.tone = LpgTone.primary,
    this.trendText,
    this.trendTone = LpgTone.success,
    this.onTap,
  });

  final String label;
  final String value;
  final String? subtitle;
  final IconData? icon;
  final LpgTone tone;

  /// Optional trend badge text (e.g. "+12.4%" or "3 pending").
  final String? trendText;
  final LpgTone trendTone;

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return LpgCard(
      onTap: onTap,
      padding: const EdgeInsets.all(LpgSpacing.md),
      semanticLabel: onTap == null ? null : '$label: $value${trendText != null ? ", $trendText" : ""}',
      child: Semantics(
        label: '$label: $value${trendText != null ? ", $trendText" : ""}',
        excludeSemantics: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (icon != null)
                  LpgIconBox(icon: icon!, tone: tone, size: LpgSizes.iconXl + 4),
                if (trendText != null)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: LpgSpacing.sm,
                      vertical: LpgSpacing.xs / 2,
                    ),
                    decoration: BoxDecoration(
                      color: trendTone.container(colors),
                      borderRadius: BorderRadius.circular(LpgRadius.full),
                      border: colors.isHighContrast
                          ? Border.all(color: trendTone.foreground(colors))
                          : null,
                    ),
                    child: Text(
                      trendText!,
                      style: text.labelSmall?.copyWith(
                        color: trendTone.foreground(colors),
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: LpgSpacing.smd),
            Text(
              value,
              style: text.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: LpgSpacing.xs / 2),
            Text(
              label,
              style: text.bodySmall?.copyWith(
                color: colors.textSecondary,
                fontWeight: FontWeight.w500,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            if (subtitle != null) ...[
              const SizedBox(height: 2),
              Text(
                subtitle!,
                style: text.labelSmall?.copyWith(
                  color: colors.textDisabled,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
