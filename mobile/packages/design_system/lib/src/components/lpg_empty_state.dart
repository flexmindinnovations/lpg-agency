import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../motion.dart';
import '../theme.dart';
import '../tone.dart';
import 'lpg_button.dart';

/// The "nothing here yet" state every list screen needs (empty orders,
/// empty notifications, empty address list): a large tinted icon, a title,
/// an optional explanation and an optional action.
class LpgEmptyState extends StatelessWidget {
  const LpgEmptyState({
    super.key,
    required this.message,
    this.title,
    this.icon = LpgIcons.empty,
    this.tone = LpgTone.primary,
    this.actionLabel,
    this.actionIcon,
    this.onAction,
  });

  /// The explanation line. Shown as the headline when [title] is null.
  final String message;
  final String? title;
  final IconData icon;
  final LpgTone tone;
  final String? actionLabel;
  final IconData? actionIcon;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(LpgSpacing.xl),
        child: LpgFadeSlideIn(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: LpgSizes.avatarLg + LpgSpacing.lg,
                height: LpgSizes.avatarLg + LpgSpacing.lg,
                decoration: BoxDecoration(
                  color: tone.container(colors),
                  shape: BoxShape.circle,
                  border: colors.isHighContrast
                      ? Border.all(color: colors.borderStrong, width: 2)
                      : null,
                ),
                child: Icon(
                  icon,
                  size: LpgSizes.iconXl + LpgSpacing.sm,
                  color: tone.foreground(colors),
                ),
              ),
              const SizedBox(height: LpgSpacing.lg),
              if (title != null) ...[
                Text(
                  title!,
                  textAlign: TextAlign.center,
                  style: text.titleMedium,
                ),
                const SizedBox(height: LpgSpacing.sm),
              ],
              Text(
                message,
                textAlign: TextAlign.center,
                style: (title == null ? text.titleSmall : text.bodyMedium)
                    ?.copyWith(
                      color: title == null
                          ? colors.textPrimary
                          : colors.textSecondary,
                    ),
              ),
              if (actionLabel != null && onAction != null) ...[
                const SizedBox(height: LpgSpacing.lg),
                LpgButton(
                  label: actionLabel!,
                  icon: actionIcon,
                  onPressed: onAction,
                  variant: LpgButtonVariant.tonal,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// A failed load: [LpgEmptyState] in the danger tone with a retry action.
/// Every screen's `AsyncValue.error` branch uses this, so failures look and
/// behave the same everywhere.
class LpgErrorState extends StatelessWidget {
  const LpgErrorState({
    super.key,
    this.title = 'Something went wrong',
    required this.message,
    this.onRetry,
    this.retryLabel = 'Try again',
  });

  final String title;
  final String message;
  final VoidCallback? onRetry;
  final String retryLabel;

  @override
  Widget build(BuildContext context) => LpgEmptyState(
    title: title,
    message: message,
    icon: LpgIcons.error,
    tone: LpgTone.danger,
    actionLabel: onRetry == null ? null : retryLabel,
    actionIcon: LpgIcons.sync,
    onAction: onRetry,
  );
}
