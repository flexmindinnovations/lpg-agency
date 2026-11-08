import 'package:flutter/material.dart';

/// The floating action button of every screen: the one primary "add" action
/// ("New order", "Add driver"). The shape, colour and text come from the
/// theme; screens never build a [FloatingActionButton] themselves.
///
/// [LpgFab.extended] carries a label, the usual choice. [LpgFab.small] is an
/// icon-only helper over a map or a long page ("Recenter map") and needs a
/// [tooltip], which is also its screen-reader name.
class LpgFab extends StatelessWidget {
  const LpgFab.extended({
    super.key,
    required this.icon,
    required String this.label,
    required this.onPressed,
    this.heroTag,
  }) : tooltip = null,
       small = false;

  const LpgFab.small({
    super.key,
    required this.icon,
    required String this.tooltip,
    required this.onPressed,
    this.heroTag,
  }) : label = null,
       small = true;

  final IconData icon;
  final String? label;
  final String? tooltip;
  final VoidCallback? onPressed;

  /// Needed when two floating buttons can be on screen at once (a page and
  /// the page above it).
  final Object? heroTag;
  final bool small;

  @override
  Widget build(BuildContext context) {
    if (small) {
      return FloatingActionButton.small(
        heroTag: heroTag,
        tooltip: tooltip,
        onPressed: onPressed,
        child: Icon(icon),
      );
    }
    return FloatingActionButton.extended(
      heroTag: heroTag,
      onPressed: onPressed,
      icon: Icon(icon),
      label: Text(label!),
    );
  }
}
