import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return LpgAdaptiveShell(
      body: navigationShell,
      selectedIndex: navigationShell.currentIndex,
      onDestinationSelected: (index) => _onTap(context, index),
      destinations: const [
        LpgNavDestination(
          icon: LpgIcons.home,
          selectedIcon: LpgIcons.homeFilled,
          label: 'Dashboard',
        ),
        LpgNavDestination(
          icon: LpgIcons.orders,
          selectedIcon: LpgIcons.ordersFilled,
          label: 'Orders',
        ),
        LpgNavDestination(
          icon: LpgIcons.support,
          selectedIcon: LpgIcons.supportFilled,
          label: 'Approvals',
        ),
        LpgNavDestination(
          icon: LpgIcons.profile,
          selectedIcon: LpgIcons.profileFilled,
          label: 'Profile',
        ),
      ],
    );
  }

  void _onTap(BuildContext context, int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }
}
