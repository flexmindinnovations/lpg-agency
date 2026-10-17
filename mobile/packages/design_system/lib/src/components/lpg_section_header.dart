import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// The title above a group of content ("Recent orders", "Today's stops"),
/// with an optional trailing text action ("See all").
class LpgSectionHeader extends StatelessWidget {
  const LpgSectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
    this.padding = const EdgeInsets.only(
      top: LpgSpacing.lg,
      bottom: LpgSpacing.smd,
    ),
  });

  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    return Padding(
      padding: padding,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Semantics(
                  header: true,
                  child: Text(title, style: text.titleMedium),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: LpgSpacing.xs / 2),
                  Text(
                    subtitle!,
                    style: text.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (actionLabel != null && onAction != null)
            TextButton(
              onPressed: onAction,
              style: TextButton.styleFrom(
                minimumSize: const Size(0, LpgSizes.touchTarget),
                padding: const EdgeInsets.symmetric(horizontal: LpgSpacing.sm),
              ),
              child: Text(actionLabel!),
            ),
        ],
      ),
    );
  }
}
