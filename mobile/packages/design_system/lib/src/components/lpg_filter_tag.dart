import 'package:flutter/material.dart';

import '../layout.dart';

/// A chip that names a filter already applied ("Ramesh Traders") and takes it
/// off when its cross is tapped. Same chip style as [LpgChoiceChips]; the
/// cross is a 48 dp target with a tooltip that doubles as its spoken name.
class LpgFilterTag extends StatelessWidget {
  const LpgFilterTag({
    super.key,
    required this.label,
    required this.onRemove,
    required this.removeTooltip,
    this.icon,
  });

  final String label;
  final VoidCallback onRemove;

  /// What removing does, in words ("Show every customer").
  final String removeTooltip;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return InputChip(
      avatar: icon == null ? null : Icon(icon, size: LpgSizes.iconSm),
      label: Text(label),
      onDeleted: onRemove,
      deleteButtonTooltipMessage: removeTooltip,
      materialTapTargetSize: MaterialTapTargetSize.padded,
    );
  }
}
