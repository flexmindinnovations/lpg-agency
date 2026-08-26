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
    final color = switch (severity) {
      LpgStatusSeverity.success => colors.statusSuccess,
      LpgStatusSeverity.warning => colors.statusWarning,
      LpgStatusSeverity.danger => colors.statusDanger,
      LpgStatusSeverity.info => colors.statusInfo,
      LpgStatusSeverity.neutral => colors.textSecondary,
    };

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: LpgTokens.spacingSm * 1.0,
        vertical: LpgTokens.spacingXs * 1.0,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(LpgTokens.radiusFull * 1.0),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: LpgTokens.typographyCaptionFontSize.toDouble(),
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
