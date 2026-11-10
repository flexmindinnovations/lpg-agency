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
        icon: Badge(
          isLabelVisible: count > 0,
          backgroundColor: colors.statusDanger,
          // Anchor the badge's trailing edge to the icon (not its leading
          // edge) so wide labels like "99+" grow inward and stay on screen.
          alignment: AlignmentDirectional.topEnd,
          offset: const Offset(4, -4),
          label: Text(count > 99 ? '99+' : '$count'),
          child: Icon(icon),
        ),
      ),
    );
  }
}
