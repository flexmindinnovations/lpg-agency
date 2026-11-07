import 'package:flutter/material.dart';

import '../haptics.dart';

/// Two or three exclusive modes shown side by side ("Phone OTP" or "Email and
/// password"): the choice changes what the screen below it shows, rather than
/// a value in a form (that is [LpgChoiceChips]). Always one option selected.
/// Colours and border come from the theme.
class LpgSegmentedControl<T> extends StatelessWidget {
  const LpgSegmentedControl({
    super.key,
    required this.options,
    required this.selected,
    required this.onSelected,
    this.icons,
  });

  /// Each value and its label, in the order shown.
  final Map<T, String> options;
  final T selected;
  final ValueChanged<T> onSelected;

  /// Optional leading icon per value.
  final Map<T, IconData>? icons;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<T>(
      segments: [
        for (final entry in options.entries)
          ButtonSegment<T>(
            value: entry.key,
            label: Text(entry.value),
            icon: icons?[entry.key] == null ? null : Icon(icons![entry.key]),
          ),
      ],
      selected: {selected},
      onSelectionChanged: (values) {
        if (values.first == selected) return;
        LpgHaptics.selection();
        onSelected(values.first);
      },
    );
  }
}
