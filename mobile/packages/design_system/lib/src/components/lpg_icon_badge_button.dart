import 'package:flutter/material.dart';

import '../theme.dart';

/// An app-bar icon button with an unread-count badge — the notifications
/// bell. The count animates in and out, caps at "99+", and is part of the
/// button's accessible label ("Notifications, 3 unread").
class LpgIconBadgeButton extends StatelessWidget {
  const LpgIconBadgeButton({
    super.key,
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.count = 0,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;
  final int count;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final label = count > 0 ? '$tooltip, $count unread' : tooltip;
    return Semantics(
      label: label,
      button: true,
      excludeSemantics: true,
      onTap: onPressed,
      child: IconButton(
        tooltip: tooltip,
        onPressed: onPressed,
        // The count pill is pinned to the icon's trailing edge (not placed by
        // its leading edge, as Badge does with a child), so a wide label like
        // "99+" grows inward and never runs off the screen edge.
        icon: Stack(
          clipBehavior: Clip.none,
          children: [
            Icon(icon),
            if (count > 0)
              PositionedDirectional(
                top: -4,
                end: -6,
                child: Badge(
                  backgroundColor: colors.statusDanger,
                  label: Text(count > 99 ? '99+' : '$count'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
