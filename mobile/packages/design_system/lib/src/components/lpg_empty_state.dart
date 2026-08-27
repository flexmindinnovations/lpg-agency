import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';
import 'lpg_button.dart';

/// The "nothing here yet" state every list screen needs (empty orders,
/// empty notifications, empty address list) — icon, message, and an
/// optional primary action, instead of each screen showing a bare `Text`
/// or nothing at all.
class LpgEmptyState extends StatelessWidget {
  const LpgEmptyState({
    super.key,
    required this.message,
    this.icon = Icons.inbox_outlined,
    this.actionLabel,
    this.onAction,
  });

  final String message;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    final isHighContrast =
        theme.brightness == Brightness.light &&
        colors.shadowLight == Colors.transparent;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(LpgTokens.spacingXl * 1.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: colors.surfaceBase,
                shape: BoxShape.circle,
                boxShadow: isHighContrast ? null : colors.neumorphicShadows,
              ),
              child: Icon(icon, size: 48, color: colors.textSecondary),
            ),
            const SizedBox(height: 32),
            Text(
              message,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colors.textSecondary,
              ),
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 32),
              LpgButton(
                label: actionLabel!,
                onPressed: onAction,
                variant: LpgButtonVariant.secondary,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
