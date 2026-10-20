import 'package:flutter/material.dart';

import '../layout.dart';
import '../theme.dart';
import 'lpg_navigation_bar.dart';

/// Caps [child] at [maxWidth] and centres it, so a phone-first screen reads
/// well on a tablet. A no-op on phones (they are narrower than the cap).
class LpgContentWidth extends StatelessWidget {
  const LpgContentWidth({
    super.key,
    required this.child,
    this.maxWidth = LpgBreakpoints.contentMaxWidth,
    this.paintCanvas = false,
  });

  final Widget child;
  final double maxWidth;

  /// Paints the page canvas either side of the column — for a full-screen
  /// route that has no shell [Scaffold] behind it.
  final bool paintCanvas;

  @override
  Widget build(BuildContext context) {
    final capped = Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: child,
      ),
    );
    if (!paintCanvas) return capped;
    return ColoredBox(color: context.lpgColors.canvas, child: capped);
  }
}

/// The app shell both apps use around their tab screens: a bottom
/// [LpgNavigationBar] on phones; on tablets (wider than
/// [LpgBreakpoints.medium]) a navigation rail on the leading edge, with the
/// tab's content capped at [LpgBreakpoints.contentMaxWidth] and centred in
/// the remaining space instead of stretched phone UI.
class LpgAdaptiveShell extends StatelessWidget {
  const LpgAdaptiveShell({
    super.key,
    required this.destinations,
    required this.selectedIndex,
    required this.onDestinationSelected,
    required this.body,
  });

  final List<LpgNavDestination> destinations;
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;
  final Widget body;

  @override
  Widget build(BuildContext context) {
    if (!LpgBreakpoints.isWide(context)) {
      return Scaffold(
        body: body,
        bottomNavigationBar: LpgNavigationBar(
          destinations: destinations,
          selectedIndex: selectedIndex,
          onDestinationSelected: onDestinationSelected,
        ),
      );
    }

    final colors = context.lpgColors;
    return Scaffold(
      body: Row(
        children: [
          _LpgNavigationRail(
            destinations: destinations,
            selectedIndex: selectedIndex,
            onDestinationSelected: onDestinationSelected,
          ),
          VerticalDivider(
            width: colors.isHighContrast ? 2 : 1,
            thickness: colors.isHighContrast ? 2 : 1,
            color: colors.isHighContrast
                ? colors.borderStrong
                : colors.borderDefault,
          ),
          Expanded(child: LpgContentWidth(child: body)),
        ],
      ),
    );
  }
}

class _LpgNavigationRail extends StatelessWidget {
  const _LpgNavigationRail({
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

    return NavigationRail(
      backgroundColor: colors.card,
      selectedIndex: selectedIndex,
      onDestinationSelected: onDestinationSelected,
      labelType: NavigationRailLabelType.all,
      groupAlignment: -1,
      minWidth: LpgSizes.touchTarget + LpgSpacing.xl,
      indicatorColor: colors.actionPrimaryContainer,
      leading: const SizedBox(height: LpgSpacing.md),
      destinations: [
        for (final d in destinations)
          NavigationRailDestination(
            icon: withBadge(d.icon, d.badgeCount),
            selectedIcon: withBadge(d.selectedIcon, d.badgeCount),
            label: Text(
              d.label,
              semanticsLabel: d.badgeCount > 0
                  ? '${d.label}, ${d.badgeCount} new'
                  : d.label,
            ),
            padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
          ),
      ],
    );
  }
}
