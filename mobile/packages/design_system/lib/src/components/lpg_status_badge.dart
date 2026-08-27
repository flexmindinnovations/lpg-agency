import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';

/// Semantic severity for [LpgStatusBadge] — deliberately separate from
/// [LpgButtonVariant]'s primary/secondary/text, since a status colour
/// (success/warning/danger) is never the app's accent colour, only ever a
/// state indicator (mirrors the web Dashboard's `StatusChipCell` /
/// `ChipSeverity` split for the same reason).
enum LpgStatusSeverity { success, warning, danger, info, neutral }

/// A small pill showing a record's status — order status, complaint
/// status, KYC verification state. Every screen that lists or details one
/// of those needs this same shape; building it once here instead of a
/// `Container`+`Text` per screen keeps severity colours consistent.
class LpgStatusBadge extends StatelessWidget {
  const LpgStatusBadge({
    super.key,
    required this.label,
    this.severity = LpgStatusSeverity.neutral,
  });

  final String label;
  final LpgStatusSeverity severity;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    final color = switch (severity) {
      LpgStatusSeverity.success => colors.statusSuccess,
      LpgStatusSeverity.warning => colors.statusWarning,
      LpgStatusSeverity.danger => colors.statusDanger,
      LpgStatusSeverity.info => colors.statusInfo,
      LpgStatusSeverity.neutral => colors.textSecondary,
    };

    final isHighContrast =
        theme.brightness == Brightness.light &&
        colors.shadowLight == Colors.transparent;

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: LpgTokens.spacingSm * 1.0,
        vertical: LpgTokens.spacingXs * 1.0,
      ),
      decoration: BoxDecoration(
        color: isHighContrast
            ? color.withValues(alpha: 0.12)
            : colors.surfaceBase,
        borderRadius: BorderRadius.circular(LpgTokens.radiusFull * 1.0),
        border: isHighContrast ? Border.all(color: color, width: 1) : null,
        boxShadow: isHighContrast
            ? null
            : [
                BoxShadow(
                  color: colors.shadowLight,
                  offset: const Offset(-2, -2),
                  blurRadius: 4,
                ),
                BoxShadow(
                  color: colors.shadowDark,
                  offset: const Offset(2, 2),
                  blurRadius: 4,
                ),
              ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!isHighContrast) ...[
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
            const SizedBox(width: 6),
          ],
          Text(
            label,
            style: TextStyle(
              color: isHighContrast ? color : colors.textPrimary,
              fontSize: LpgTokens.typographyCaptionFontSize.toDouble() - 1,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}
