import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import '../tone.dart';
import 'lpg_card.dart';
import 'lpg_icon_box.dart';

/// One number with its label: "3 stops left", "₹1,240 collected". Lay
/// several out in a `Row` of `Expanded`s for a dashboard strip.
class LpgStatTile extends StatelessWidget {
  const LpgStatTile({
    super.key,
    required this.label,
    required this.value,
    this.icon,
    this.tone = LpgTone.primary,
    this.onTap,
  });

  final String label;
  final String value;
  final IconData? icon;
  final LpgTone tone;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    return LpgCard(
      onTap: onTap,
      padding: const EdgeInsets.all(LpgSpacing.md),
      semanticLabel: onTap == null ? null : '$label: $value',
      child: Semantics(
        label: '$label: $value',
        excludeSemantics: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (icon != null) ...[
              LpgIconBox(icon: icon!, tone: tone, size: LpgSizes.iconXl + 4),
              const SizedBox(height: LpgSpacing.smd),
            ],
            Text(
              value,
              style: text.headlineSmall,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: LpgSpacing.xs / 2),
            Text(
              label,
              style: text.bodySmall,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
