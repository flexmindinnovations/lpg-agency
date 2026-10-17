import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../motion.dart';
import '../theme.dart';

/// A minus / count / plus control for small whole quantities (cylinders to
/// order, cylinders delivered). The count animates between values, the
/// buttons are full 48dp targets, and the whole control is announced as an
/// adjustable value ("Quantity, 2") that screen-reader swipes change.
class LpgQuantityStepper extends StatelessWidget {
  const LpgQuantityStepper({
    super.key,
    required this.value,
    required this.onChanged,
    this.min = 0,
    this.max,
    this.semanticLabel = 'Quantity',
  });

  final int value;
  final ValueChanged<int>? onChanged;
  final int min;
  final int? max;
  final String semanticLabel;

  bool get _canDecrement => onChanged != null && value > min;
  bool get _canIncrement => onChanged != null && (max == null || value < max!);

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;

    Widget button(IconData icon, String tooltip, bool enabled, int next) =>
        IconButton.filledTonal(
          tooltip: tooltip,
          onPressed: enabled ? () => onChanged!(next) : null,
          style: IconButton.styleFrom(
            backgroundColor: colors.actionPrimaryContainer,
            foregroundColor: colors.onActionPrimaryContainer,
            disabledBackgroundColor: colors.surfaceOverlay,
            disabledForegroundColor: colors.textDisabled,
            minimumSize: const Size.square(LpgSizes.touchTarget),
            side: colors.isHighContrast
                ? BorderSide(color: colors.borderStrong, width: 2)
                : null,
          ),
          icon: Icon(icon, size: LpgSizes.iconMd),
        );

    return Semantics(
      label: semanticLabel,
      value: '$value',
      increasedValue: _canIncrement ? '${value + 1}' : null,
      decreasedValue: _canDecrement ? '${value - 1}' : null,
      onIncrease: _canIncrement ? () => onChanged!(value + 1) : null,
      onDecrease: _canDecrement ? () => onChanged!(value - 1) : null,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          button(LpgIcons.remove, 'Decrease', _canDecrement, value - 1),
          SizedBox(
            width: LpgSizes.touchTarget,
            child: AnimatedSwitcher(
              duration: LpgMotion.small(context),
              transitionBuilder: (child, animation) => ScaleTransition(
                scale: animation,
                child: FadeTransition(opacity: animation, child: child),
              ),
              child: Text(
                '$value',
                key: ValueKey(value),
                textAlign: TextAlign.center,
                style: context.lpgText.headlineSmall,
              ),
            ),
          ),
          button(LpgIcons.add, 'Increase', _canIncrement, value + 1),
        ],
      ),
    );
  }
}
