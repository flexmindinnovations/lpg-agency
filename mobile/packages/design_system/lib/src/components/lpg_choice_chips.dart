import 'package:flutter/material.dart';

import '../glass.dart';
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
    const shape = StadiumBorder();
    void choose(T key, bool isSelected) {
      LpgHaptics.selection();
      if (isSelected) {
        onSelected(key);
      } else if (allowDeselect) {
        onSelected(null);
      }
    }

    return Wrap(
      spacing: LpgSpacing.sm,
      runSpacing: LpgSpacing.sm,
      children: [
        for (final entry in options.entries)
          // Every chip keeps a 48px touch target, whichever row it wraps onto
          // (CA-14): the chip itself is shrink-wrapped so the fill and the
          // paper grain under it fit the visible pill, and this box restores
          // the target around it.
          Semantics(
            container: true,
            button: true,
            selected: entry.key == selected,
            inMutuallyExclusiveGroup: true,
            label: entry.value,
            onTap: () => choose(entry.key, entry.key != selected),
            excludeSemantics: true,
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => choose(entry.key, entry.key != selected),
              child: ConstrainedBox(
                constraints: const BoxConstraints(
                  minHeight: LpgSizes.touchTarget,
                ),
                child: Center(
                  widthFactor: 1,
                  child: DecoratedBox(
                    decoration: ShapeDecoration(
                      color: colors.isHighContrast
                          ? null
                          : entry.key == selected
                          ? colors.actionPrimaryContainer
                          : colors.cardGlass,
                      shape: shape,
                    ),
                    child: LpgGrainLayer(
                      shape: shape,
                      strength: entry.key == selected
                          ? LpgGlassLook.solidGrain
                          : LpgGlassLook.of(colors).surfaceGrain,
                      child: ChoiceChip(
                        backgroundColor: colors.isHighContrast
                            ? null
                            : Colors.transparent,
                        selectedColor: colors.isHighContrast
                            ? null
                            : Colors.transparent,
                        label: Text(entry.value),
                        selected: entry.key == selected,
                        showCheckmark: icons?[entry.key] == null,
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
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
                        onSelected: (isSelected) =>
                            choose(entry.key, isSelected),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
