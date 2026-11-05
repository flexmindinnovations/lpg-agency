import 'package:flutter/material.dart';

import '../layout.dart';
import '../motion.dart';
import '../theme.dart';
import '../tone.dart';

/// Semantic severity for [LpgStatusBadge] — deliberately separate from
/// [LpgButtonVariant]'s primary/secondary/text, since a status colour
/// (success/warning/danger) is never the app's accent colour, only ever a
/// state indicator (mirrors the web Dashboard's `StatusChipCell` /
/// `ChipSeverity` split for the same reason).
enum LpgStatusSeverity { success, warning, danger, info, neutral }

extension LpgStatusSeverityTone on LpgStatusSeverity {
  LpgTone get tone => switch (this) {
    LpgStatusSeverity.success => LpgTone.success,
    LpgStatusSeverity.warning => LpgTone.warning,
    LpgStatusSeverity.danger => LpgTone.danger,
    LpgStatusSeverity.info => LpgTone.info,
    LpgStatusSeverity.neutral => LpgTone.neutral,
  };
}

/// A small pill showing a record's status — order status, complaint
/// status, KYC verification state. Building it once here instead of a
/// `Container`+`Text` per screen keeps severity colours consistent.
class LpgStatusBadge extends StatelessWidget {
  const LpgStatusBadge({
    super.key,
    required this.label,
    this.severity = LpgStatusSeverity.neutral,
    this.icon,
    this.isLive = false,
  });

  final String label;
  final LpgStatusSeverity severity;

  /// Replaces the leading status dot.
  final IconData? icon;

  /// Shows a pulsing animation on the leading dot for active / live statuses.
  final bool isLive;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final tone = severity.tone;
    final color = tone.foreground(colors);

    Widget dot = Container(
      width: LpgSpacing.sm - 2,
      height: LpgSpacing.sm - 2,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );

    if (isLive && !colors.isHighContrast) {
      dot = _LiveDot(color: color, child: dot);
    }

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: LpgSpacing.sm + LpgSpacing.xs / 2,
        vertical: LpgSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: tone.container(colors),
        borderRadius: BorderRadius.circular(LpgRadius.full),
        border: colors.isHighContrast ? Border.all(color: color) : null,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: LpgSizes.iconSm - LpgSpacing.xs, color: color),
            const SizedBox(width: LpgSpacing.xs),
          ] else if (!colors.isHighContrast) ...[
            dot,
            const SizedBox(width: LpgSpacing.xs + 2),
          ],
          Text(
            label,
            style: context.lpgText.labelSmall?.copyWith(
              color: colors.isHighContrast ? color : colors.textPrimary,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _LiveDot extends StatefulWidget {
  const _LiveDot({required this.color, required this.child});

  final Color color;
  final Widget child;

  @override
  State<_LiveDot> createState() => _LiveDotState();
}

class _LiveDotState extends State<_LiveDot> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: LpgMotion.pulse,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) {
      _controller.stop();
    } else if (!_controller.isAnimating && _controller.value == 0) {
      _controller.repeat(count: LpgMotion.pulseRepeats, reverse: true);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      child: widget.child,
      builder: (context, child) {
        return Opacity(
          opacity: 0.4 + (0.6 * _controller.value),
          child: child,
        );
      },
    );
  }
}
