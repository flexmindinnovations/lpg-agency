import 'package:flutter/material.dart';

import '../haptics.dart';
import '../layout.dart';
import '../theme.dart';

/// A single-select row of chips — payment method, cylinder size, a list
/// filter. Better than a dropdown when there are only a handful of options,
/// because every option is visible and one tap away. The border comes from the
/// theme's chip style, the same as the filter chips on a list screen, and does
/// not change when a chip is selected (the fill and the check mark do).
///
/// [options] maps each value to its label. With [allowDeselect], tapping the
/// selected chip clears the selection (passes `null`).
///
/// [LpgChoiceChips.filterRow] is the same chips in one row that scrolls
/// sideways, under a list's search box ("All", "Open", "Resolved"). A `null`
/// key is a valid value there: "All" is `null: 'All'`.
class LpgChoiceChips<T> extends StatelessWidget {
  const LpgChoiceChips({
    super.key,
    required this.options,
    required this.selected,
    required this.onSelected,
    this.icons,
    this.allowDeselect = false,
  }) : scrollable = false;

  const LpgChoiceChips.filterRow({
    super.key,
    required this.options,
    required this.selected,
    required this.onSelected,
  }) : icons = null,
       allowDeselect = false,
       scrollable = true;

  final Map<T, String> options;
  final T? selected;
  final ValueChanged<T?> onSelected;

  /// Optional leading icon per value.
  final Map<T, IconData>? icons;
  final bool allowDeselect;

  /// One row that scrolls sideways, with the page's side padding, instead of
  /// wrapping onto more lines.
  final bool scrollable;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final chips = [
      for (final entry in options.entries)
        ChoiceChip(
          label: Text(entry.value),
          selected: entry.key == selected,
          showCheckmark: icons?[entry.key] == null,
          // Every chip keeps a 48px touch target, whichever row it
          // wraps onto (CA-14).
          materialTapTargetSize: MaterialTapTargetSize.padded,
          avatar: icons?[entry.key] == null
              ? null
              : Icon(
                  icons![entry.key],
                  size: LpgSizes.iconSm + 2,
                  color: entry.key == selected
                      ? colors.onActionPrimaryContainer
                      : colors.textSecondary,
                ),
          labelStyle: context.lpgText.labelLarge?.copyWith(
            color: entry.key == selected
                ? colors.onActionPrimaryContainer
                : colors.textPrimary,
          ),
          onSelected: (isSelected) {
            LpgHaptics.selection();
            if (isSelected) {
              onSelected(entry.key);
            } else if (allowDeselect) {
              onSelected(null);
            }
          },
        ),
    ];
    if (!scrollable) {
      return Wrap(
        spacing: LpgSpacing.sm,
        runSpacing: LpgSpacing.sm,
        children: chips,
      );
    }
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(
        horizontal: LpgSpacing.md,
        vertical: LpgSpacing.sm,
      ),
      child: Row(
        children: [
          for (var i = 0; i < chips.length; i++) ...[
            if (i > 0) const SizedBox(width: LpgSpacing.sm),
            chips[i],
          ],
        ],
      ),
    );
  }
}
