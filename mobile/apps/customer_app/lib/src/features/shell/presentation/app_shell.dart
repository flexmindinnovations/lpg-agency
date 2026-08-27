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
        margin: EdgeInsets.only(
          left: 20,
          right: 20,
          bottom: MediaQuery.of(context).padding.bottom + 10,
        ),
        decoration: BoxDecoration(
          color: colors.surfaceBase,
          borderRadius: BorderRadius.circular(LpgTokens.radiusFull * 1.0),
          boxShadow: [
            BoxShadow(
              color: colors.shadowLight,
              offset: const Offset(-4, -4),
              blurRadius: 10,
            ),
            BoxShadow(
              color: colors.shadowDark,
              offset: const Offset(4, 4),
              blurRadius: 10,
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(LpgTokens.radiusFull * 1.0),
          child: NavigationBar(
            backgroundColor: Colors.transparent,
            elevation: 0,
            height: 64,
            indicatorColor: colors.actionPrimary.withValues(alpha: 0.12),
            labelBehavior: NavigationDestinationLabelBehavior.alwaysHide,
            selectedIndex: navigationShell.currentIndex,
            onDestinationSelected: (int index) => _onTap(context, index),
            destinations: [
              NavigationDestination(
                icon: Icon(Icons.home_outlined, color: colors.textSecondary),
                selectedIcon: Icon(Icons.home, color: colors.actionPrimary),
                label: 'Home',
              ),
              NavigationDestination(
                icon: Icon(
                  Icons.receipt_long_outlined,
                  color: colors.textSecondary,
                ),
                selectedIcon: Icon(
                  Icons.receipt_long,
                  color: colors.actionPrimary,
                ),
                label: 'Orders',
              ),
              NavigationDestination(
                icon: Icon(
                  Icons.support_agent_outlined,
                  color: colors.textSecondary,
                ),
                selectedIcon: Icon(
                  Icons.support_agent,
                  color: colors.actionPrimary,
                ),
                label: 'Support',
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

  void _onTap(BuildContext context, int index) {
    navigationShell.goBranch(
      index,
      // Support navigating to the initial location when tapping the item that is already active
      initialLocation: index == navigationShell.currentIndex,
    );
  }
}
