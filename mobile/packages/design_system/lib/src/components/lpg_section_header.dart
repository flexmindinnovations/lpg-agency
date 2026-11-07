import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';

/// The title above a group of content ("Recent orders", "Today's stops"),
/// with an optional trailing text action ("See all").
///
/// The one section heading of every app: sentence case (never capitals, never
/// Title Case) in the normal weight, in the main text colour. Write the title
/// that way; the widget does not change its case.
///
/// Spacing is owned here, so no screen sets it: a heading has [LpgSpacing.lg]
/// of space above it to separate it from what came before, except when it is
/// the very first child of a scrolling list, where the page's own padding
/// already separates it from the app bar and the extra space would double up.
class LpgSectionHeader extends StatelessWidget {
  const LpgSectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
    this.padding,
  });

  /// A heading the layout already spaces (inside a sheet or a form column):
  /// the same style, no outer padding, no subtitle, no action.
  const LpgSectionHeader.compact({super.key, required this.title})
    : subtitle = null,
      actionLabel = null,
      onAction = null,
      padding = EdgeInsets.zero;

  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  /// Overrides the automatic spacing. Leave it out.
  final EdgeInsetsGeometry? padding;

  static const _below = LpgSpacing.smd;

  /// True when this heading is the first child of a list: the nearest
  /// [IndexedSemantics] (which every list child is wrapped in) is index 0 and
  /// nothing that lays out several children ([Flex], [Stack], [Wrap]) sits
  /// between, so it really is the first thing on the page.
  static bool _isFirstInList(BuildContext context) {
    var first = false;
    context.visitAncestorElements((element) {
      final widget = element.widget;
      if (widget is Flex || widget is Stack || widget is Wrap) return false;
      if (widget is IndexedSemantics) {
        first = widget.index == 0;
        return false;
      }
      return true;
    });
    return first;
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final spacing =
        padding ??
        EdgeInsets.only(
          top: _isFirstInList(context) ? 0 : LpgSpacing.lg,
          bottom: _below,
        );
    return Padding(
      padding: spacing,
      child: Row(
        // Centred, so a trailing "See all" lines up with the title rather
        // than sitting on the subtitle's baseline (CA-14).
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Semantics(
                  header: true,
                  child: Text(
                    title,
                    style: text.titleMedium?.copyWith(
                      fontWeight: FontWeight.w400,
                    ),
                  ),
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
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(actionLabel!),
                  const SizedBox(width: LpgSpacing.xs),
                  const Icon(LpgIcons.chevronRight, size: LpgSizes.iconSm),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
