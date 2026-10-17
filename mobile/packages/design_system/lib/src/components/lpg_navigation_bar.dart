import 'package:flutter/material.dart';

import '../motion.dart';
import '../theme.dart';

/// One tab of an [LpgNavigationBar].
@immutable
class LpgNavDestination {
  const LpgNavDestination({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    this.badgeCount = 0,
  });

  final IconData icon;

  /// The filled variant, so the active tab is marked by weight as well as
  /// colour.
  final IconData selectedIcon;
  final String label;

  /// Shows a count badge on the icon when above zero.
  final int badgeCount;
}

/// The bottom navigation bar both apps' shells use. A themed Material 3
/// [NavigationBar] (pill indicator, filled selected icon) on the card
/// surface, lifted off content by the floating shadow — or, in high
/// contrast, a 2px top border.
class LpgNavigationBar extends StatelessWidget {
  const LpgNavigationBar({
    super.key,
    required this.destinations,
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  final List<LpgNavDestination> destinations;
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;

    Widget withBadge(IconData icon, int count) => count > 0
        ? Badge(label: Text(count > 99 ? '99+' : '$count'), child: Icon(icon))
        : Icon(icon);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.card,
        border: Border(
          top: BorderSide(
            color: colors.isHighContrast
                ? colors.borderStrong
                : colors.borderDefault,
            width: colors.isHighContrast ? 2 : 1,
          ),
        ),
      ),
      child: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: onDestinationSelected,
        animationDuration: LpgMotion.large(context),
        destinations: [
          for (final d in destinations)
            NavigationDestination(
              icon: withBadge(d.icon, d.badgeCount),
              selectedIcon: withBadge(d.selectedIcon, d.badgeCount),
              label: d.label,
              tooltip: d.badgeCount > 0
                  ? '${d.label}, ${d.badgeCount} new'
                  : d.label,
            ),
        ],
      ),
    );
  }
}
