import 'package:flutter/material.dart';

import '../layout.dart';
import '../motion.dart';
import '../theme.dart';

/// Segment item configuration for [LpgSegmentedControl].
@immutable
class LpgSegmentItem<T> {
  const LpgSegmentItem({
    required this.value,
    required this.label,
    this.badgeCount,
    this.icon,
  });

  final T value;
  final String label;
  final int? badgeCount;
  final IconData? icon;
}

/// An M3 Expressive segmented control / filter bar with animated selection pill,
/// responsive target sizing, and optional badge counters.
class LpgSegmentedControl<T> extends StatelessWidget {
  const LpgSegmentedControl({
    super.key,
    required this.segments,
    required this.selectedValue,
    required this.onValueChanged,
    this.padding = const EdgeInsets.all(LpgSpacing.xs),
  });

  final List<LpgSegmentItem<T>> segments;
  final T selectedValue;
  final ValueChanged<T> onValueChanged;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final selectedIndex = segments.indexWhere((s) => s.value == selectedValue);

    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: colors.surfaceOverlay,
        borderRadius: BorderRadius.circular(LpgRadius.lg),
        border: colors.isHighContrast
            ? Border.all(color: colors.borderStrong, width: 2)
            : null,
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final count = segments.length;
          final itemWidth = (constraints.maxWidth - (padding.horizontal)) / count;

          return Stack(
            children: [
              // Animated Indicator Pill
              if (selectedIndex >= 0)
                AnimatedPositioned(
                  duration: LpgMotion.medium(context),
                  curve: Curves.fastOutSlowIn,
                  left: selectedIndex * itemWidth,
                  top: 0,
                  bottom: 0,
                  width: itemWidth,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: colors.card,
                      borderRadius: BorderRadius.circular(LpgRadius.md),
                      boxShadow: colors.isHighContrast ? null : colors.cardShadow,
                      border: colors.isHighContrast
                          ? Border.all(color: colors.borderFocus, width: 2)
                          : null,
                    ),
                  ),
                ),

              // Segment Items
              Row(
                children: [
                  for (final item in segments) ...[
                    Expanded(
                      child: InkWell(
                        onTap: () => onValueChanged(item.value),
                        borderRadius: BorderRadius.circular(LpgRadius.md),
                        child: Container(
                          height: LpgSizes.buttonHeight - LpgSpacing.sm,
                          alignment: Alignment.center,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              if (item.icon != null) ...[
                                Icon(
                                  item.icon,
                                  size: LpgSizes.iconSm,
                                  color: item.value == selectedValue
                                      ? colors.actionPrimary
                                      : colors.textSecondary,
                                ),
                                const SizedBox(width: LpgSpacing.xs),
                              ],
                              Flexible(
                                child: Text(
                                  item.label,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: text.labelMedium?.copyWith(
                                    fontWeight: item.value == selectedValue
                                        ? FontWeight.bold
                                        : FontWeight.w500,
                                    color: item.value == selectedValue
                                        ? colors.textPrimary
                                        : colors.textSecondary,
                                  ),
                                ),
                              ),
                              if (item.badgeCount != null && item.badgeCount! > 0) ...[
                                const SizedBox(width: LpgSpacing.xs),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: LpgSpacing.xs + 2,
                                    vertical: 2,
                                  ),
                                  decoration: BoxDecoration(
                                    color: item.value == selectedValue
                                        ? colors.actionPrimaryContainer
                                        : colors.borderDefault,
                                    borderRadius: BorderRadius.circular(LpgRadius.full),
                                  ),
                                  child: Text(
                                    '${item.badgeCount}',
                                    style: text.labelSmall?.copyWith(
                                      color: item.value == selectedValue
                                          ? colors.onActionPrimaryContainer
                                          : colors.textSecondary,
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}
