import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import '../tone.dart';
import 'lpg_icon_box.dart';

/// A themed list row — order, complaint, notification and address rows.
///
/// Leading icon on a tinted square ([LpgIconBox]), title and optional
/// subtitle, free-form trailing content, and an optional chevron for rows
/// that open a detail screen. Rows are at least [LpgSizes.touchTarget] tall.
class LpgListTile extends StatelessWidget {
  const LpgListTile({
    super.key,
    required this.title,
    this.subtitle,
    this.leadingIcon,
    this.leadingTone = LpgTone.primary,
    this.leading,
    this.trailing,
    this.onTap,
    this.showChevron = false,
    this.dense = false,
  });

  final String title;
  final String? subtitle;
  final IconData? leadingIcon;
  final LpgTone leadingTone;

  /// A custom leading widget (an avatar, say), used instead of
  /// [leadingIcon].
  final Widget? leading;

  /// Free-form trailing content — a status badge, a timestamp, an amount.
  final Widget? trailing;
  final VoidCallback? onTap;

  /// Shows a trailing chevron after [trailing], signalling navigation.
  final bool showChevron;

  /// Tighter vertical padding for rows nested inside a card.
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final leadingWidget =
        leading ??
        (leadingIcon == null
            ? null
            : LpgIconBox(icon: leadingIcon!, tone: leadingTone));

    final row = ConstrainedBox(
      constraints: const BoxConstraints(minHeight: LpgSizes.touchTarget),
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: LpgSpacing.md,
          vertical: dense ? LpgSpacing.sm : LpgSpacing.smd,
        ),
        child: Row(
          children: [
            if (leadingWidget != null) ...[
              leadingWidget,
              const SizedBox(width: LpgSpacing.smd),
            ],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    title,
                    style: text.titleSmall,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: LpgSpacing.xs / 2),
                    Text(
                      subtitle!,
                      style: text.bodySmall?.copyWith(
                        color: colors.textSecondary,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            if (trailing != null) ...[
              const SizedBox(width: LpgSpacing.smd),
              trailing!,
            ],
            if (showChevron) ...[
              const SizedBox(width: LpgSpacing.xs),
              Icon(
                LpgIcons.chevronRight,
                size: LpgSizes.iconSm,
                color: colors.textSecondary,
              ),
            ],
          ],
        ),
      ),
    );

    if (onTap == null) return row;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(LpgRadius.lg),
      child: row,
    );
  }
}
