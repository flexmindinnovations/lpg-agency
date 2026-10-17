import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import '../tone.dart';
import 'lpg_card.dart';
import 'lpg_icon_box.dart';

/// A square shortcut tile — icon over label — for a dashboard's grid of
/// frequent destinations (Invoices, KYC, Support, Van load).
class LpgQuickAction extends StatelessWidget {
  const LpgQuickAction({
    super.key,
    required this.icon,
    required this.label,
    required this.onTap,
    this.tone = LpgTone.primary,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final LpgTone tone;

  @override
  Widget build(BuildContext context) {
    return LpgCard(
      onTap: onTap,
      semanticLabel: label,
      padding: const EdgeInsets.symmetric(
        horizontal: LpgSpacing.sm,
        vertical: LpgSpacing.md,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          LpgIconBox(icon: icon, tone: tone),
          const SizedBox(height: LpgSpacing.sm),
          Text(
            label,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: context.lpgText.labelMedium?.copyWith(
              color: context.lpgColors.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
