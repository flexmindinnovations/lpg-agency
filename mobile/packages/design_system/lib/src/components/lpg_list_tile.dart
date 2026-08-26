import 'package:flutter/material.dart';

import '../theme.dart';
import '../tokens.dart';

/// A themed list row — order/complaint/notification list items, address
/// rows on the Profile screen. Mirrors `dashboard_screen.dart`'s
/// hand-built `_buildActivityItem` (icon in a bordered circle, title,
/// trailing text) so that one-off gets replaced by a shared widget instead
/// of every new list screen re-implementing the same row shape.
class LpgListTile extends StatelessWidget {
  const LpgListTile({
    super.key,
    required this.title,
    this.subtitle,
    this.leadingIcon,
    this.trailing,
    this.onTap,
  });

  final String title;
  final String? subtitle;
  final IconData? leadingIcon;

  /// Free-form trailing content — a status badge, a timestamp, an amount.
  final Widget? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    final row = Padding(
      padding: const EdgeInsets.symmetric(vertical: LpgTokens.spacingSm * 1.0),
      child: Row(
        children: [
          if (leadingIcon != null) ...[
            Container(
              padding: const EdgeInsets.all(LpgTokens.spacingSm * 1.0),
              decoration: BoxDecoration(
                color: colors.surfaceRaised,
                shape: BoxShape.circle,
                border: Border.all(color: colors.borderDefault),
              ),
              child: Icon(leadingIcon, size: 16, color: colors.textSecondary),
            ),
            const SizedBox(width: LpgTokens.spacingMd * 1.0),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    subtitle!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: LpgTokens.spacingMd * 1.0),
            trailing!,
          ],
        ],
      ),
    );

    if (onTap == null) return row;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(LpgTokens.radiusMd * 1.0),
      child: row,
    );
  }
}
