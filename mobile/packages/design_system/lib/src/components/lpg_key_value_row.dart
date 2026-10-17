import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// A label/value pair on one line — the building block of every detail
/// card (order details, invoice totals, delivery info). [emphasize] makes
/// the row a total: bolder and larger.
class LpgKeyValueRow extends StatelessWidget {
  const LpgKeyValueRow({
    super.key,
    required this.label,
    required this.value,
    this.icon,
    this.emphasize = false,
    this.valueColor,
    this.trailing,
  });

  final String label;
  final String value;
  final IconData? icon;
  final bool emphasize;
  final Color? valueColor;

  /// Replaces the value text, e.g. with a status badge.
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs + 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (icon != null) ...[
            Icon(icon, size: LpgSizes.iconSm + 2, color: colors.textSecondary),
            const SizedBox(width: LpgSpacing.sm),
          ],
          Expanded(
            flex: 2,
            child: Text(
              label,
              style: (emphasize ? text.titleSmall : text.bodyMedium)?.copyWith(
                color: emphasize ? colors.textPrimary : colors.textSecondary,
              ),
            ),
          ),
          const SizedBox(width: LpgSpacing.md),
          Flexible(
            flex: 3,
            child: Align(
              alignment: Alignment.centerRight,
              child:
                  trailing ??
                  Text(
                    value,
                    textAlign: TextAlign.right,
                    style: (emphasize ? text.titleMedium : text.bodyMedium)
                        ?.copyWith(
                          color: valueColor ?? colors.textPrimary,
                          fontWeight: emphasize
                              ? FontWeight.w700
                              : FontWeight.w600,
                        ),
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
