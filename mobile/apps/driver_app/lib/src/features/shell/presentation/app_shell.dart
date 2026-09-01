import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

/// The Driver App shell: a persistent bottom `NavigationBar` across the three
/// tabs (Today / Deliveries / Profile). Mirrors the Customer App's
/// `AppShell` — same edge-to-edge bar and high-contrast treatment.
class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = Theme.of(context).extension<LpgColors>()!;

    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          border: colors.isHighContrast
              ? Border(top: BorderSide(color: colors.borderStrong, width: 2))
              : null,
        ),
        child: Material(
          color: colors.surfaceRaised,
          elevation: colors.isHighContrast ? 0 : 3,
          child: NavigationBar(
            backgroundColor: Colors.transparent,
            elevation: 0,
            indicatorColor: colors.actionPrimary.withValues(alpha: 0.12),
            labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
            selectedIndex: navigationShell.currentIndex,
            onDestinationSelected: _onTap,
            destinations: [
              NavigationDestination(
                icon: Icon(Icons.today_outlined, color: colors.textSecondary),
                selectedIcon: Icon(Icons.today, color: colors.actionPrimary),
                label: 'Today',
              ),
              NavigationDestination(
                icon: Icon(
                  Icons.local_shipping_outlined,
                  color: colors.textSecondary,
                ),
                selectedIcon: Icon(
                  Icons.local_shipping,
                  color: colors.actionPrimary,
                ),
                label: 'Deliveries',
              ),
              NavigationDestination(
                icon: Icon(Icons.person_outline, color: colors.textSecondary),
                selectedIcon: Icon(Icons.person, color: colors.actionPrimary),
                label: 'Profile',
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _onTap(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }
}
