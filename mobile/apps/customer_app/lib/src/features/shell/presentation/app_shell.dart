import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// The main application shell for the Customer App.
///
/// Provides a persistent bottom navigation bar across the four main tabs:
/// Dashboard, Orders, Support, and Profile.
class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.navigationShell});

  /// The navigation shell and state for the branches.
  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;

    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(color: colors.borderDefault, width: 1),
          ),
        ),
        child: BottomNavigationBar(
          backgroundColor: colors.surfaceRaised,
          type: BottomNavigationBarType.fixed,
          selectedItemColor: colors.textPrimary,
          unselectedItemColor: colors.textSecondary,
          showSelectedLabels: true,
          showUnselectedLabels: true,
          currentIndex: navigationShell.currentIndex,
          onTap: (int index) => _onTap(context, index),
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.home_outlined),
              activeIcon: Icon(Icons.home),
              label: 'Home',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.receipt_long_outlined),
              activeIcon: Icon(Icons.receipt_long),
              label: 'Orders',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.support_agent_outlined),
              activeIcon: Icon(Icons.support_agent),
              label: 'Support',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.person_outline),
              activeIcon: Icon(Icons.person),
              label: 'Profile',
            ),
          ],
        ),
      ),
    );
  }

  void _onTap(BuildContext context, int index) {
    navigationShell.goBranch(
      index,
      // Support navigating to the initial location when tapping the item that is already active
      initialLocation: index == navigationShell.currentIndex,
    );
  }
}
