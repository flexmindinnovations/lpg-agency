import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import 'lpg_card.dart';
import 'lpg_cylinder_illustration.dart';
import 'lpg_quantity_stepper.dart';
import 'lpg_status_badge.dart';

/// Domain-driven card component for LPG Cylinders.
///
/// Used in Customer booking, Driver van load counts, and Admin inventory lists.
class LpgCylinderCard extends StatelessWidget {
  const LpgCylinderCard({
    super.key,
    required this.title,
    required this.size,
    this.subtitle,
    this.priceText,
    this.state = LpgCylinderState.full,
    this.quantity,
    this.onQuantityChanged,
    this.minQuantity = 0,
    this.maxQuantity,
    this.onTap,
    this.statusLabel,
    this.statusSeverity = LpgStatusSeverity.neutral,
    this.selected = false,
  });

  final String title;
  final LpgCylinderSize size;
  final String? subtitle;
  final String? priceText;
  final LpgCylinderState state;

  /// When non-null with [onQuantityChanged], shows a quantity stepper.
  final int? quantity;
  final ValueChanged<int>? onQuantityChanged;
  final int minQuantity;
  final int? maxQuantity;

  final VoidCallback? onTap;

  /// Optional custom status pill label.
  final String? statusLabel;
  final LpgStatusSeverity statusSeverity;

  final bool selected;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final cardVariant = selected
        ? LpgCardVariant.tonal
        : LpgCardVariant.elevated;

    return LpgCard(
      onTap: onTap,
      variant: cardVariant,
      semanticLabel: '$title${priceText != null ? ", $priceText" : ""}',
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Cylinder Illustration
          Padding(
            padding: const EdgeInsets.only(right: LpgSpacing.md),
            child: LpgCylinderIllustration(
              size: size,
              state: state,
              height: 56.0,
            ),
          ),

          // Title & Subtitle Info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: text.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (statusLabel != null)
                      LpgStatusBadge(
                        label: statusLabel!,
                        severity: statusSeverity,
                      ),
                  ],
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: LpgSpacing.xs / 2),
                  Text(
                    subtitle!,
                    style: text.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                if (priceText != null) ...[
                  const SizedBox(height: LpgSpacing.xs),
                  Text(
                    priceText!,
                    style: text.titleSmall?.copyWith(
                      color: colors.actionPrimary,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ],
            ),
          ),

          // Interactive Quantity Stepper or Count Badge
          if (quantity != null && onQuantityChanged != null) ...[
            const SizedBox(width: LpgSpacing.sm),
            LpgQuantityStepper(
              value: quantity!,
              onChanged: onQuantityChanged,
              min: minQuantity,
              max: maxQuantity,
              semanticLabel: 'Quantity for $title',
            ),
          ] else if (quantity != null) ...[
            const SizedBox(width: LpgSpacing.md),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: LpgSpacing.md,
                vertical: LpgSpacing.xs,
              ),
              decoration: BoxDecoration(
                color: colors.actionPrimaryContainer,
                borderRadius: BorderRadius.circular(LpgRadius.full),
              ),
              child: Text(
                'x$quantity',
                style: text.labelLarge?.copyWith(
                  color: colors.onActionPrimaryContainer,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
