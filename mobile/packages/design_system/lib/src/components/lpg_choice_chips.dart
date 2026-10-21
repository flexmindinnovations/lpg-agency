import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';

/// A single-select row of chips — payment method, cylinder size, a list
/// filter. Better than a dropdown when there are only a handful of options,
/// because every option is visible and one tap away.
///
/// [options] maps each value to its label. With [allowDeselect], tapping the
/// selected chip clears the selection (passes `null`).
class LpgChoiceChips<T> extends StatelessWidget {
  const LpgChoiceChips({
    super.key,
    required this.options,
    required this.selected,
    required this.onSelected,
    this.icons,
    this.allowDeselect = false,
  });

  final Map<T, String> options;
  final T? selected;
  final ValueChanged<T?> onSelected;

  /// Optional leading icon per value.
  final Map<T, IconData>? icons;
  final bool allowDeselect;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Wrap(
      spacing: LpgSpacing.sm,
      runSpacing: LpgSpacing.sm,
      children: [
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
            side: BorderSide(
              color: entry.key == selected
                  ? colors.actionPrimary
                  : colors.borderDefault,
              width: colors.isHighContrast ? 2 : 1,
            ),
            onSelected: (isSelected) {
              if (isSelected) {
                onSelected(entry.key);
              } else if (allowDeselect) {
                onSelected(null);
              }
            },
          ),
      ],
    );
  }
}
