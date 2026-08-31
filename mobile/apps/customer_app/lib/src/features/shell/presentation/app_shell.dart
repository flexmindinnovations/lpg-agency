import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../dashboard/data/notifications_provider.dart';

/// The main application shell for the Customer App.
///
/// Provides a persistent bottom navigation bar across the four main tabs:
/// Dashboard, Orders, Support, and Profile. Also the one place that's
/// always mounted while the app is in use, so it's where the app-wide
/// `notification.new` real-time subscription lives -- every screen's
/// unread badge/list should reflect a new notification without a manual
/// refresh, not just the Notifications screen itself.
class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.navigationShell});

  /// The navigation shell and state for the branches.
  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(notificationsRealtimeProvider, (previous, next) {
      next.whenData((_) {
        ref.invalidate(notificationsProvider);
        ref.invalidate(unreadNotificationCountProvider);
      });
    });

    final colors = Theme.of(context).extension<LpgColors>()!;

    return Scaffold(
      body: navigationShell,
      // Edge-to-edge bar, flush with the screen — no floating-pill margin.
      // Real Material elevation (with M3's surface tint) lifts it off the
      // content; high-contrast mode swaps that for an explicit top border
      // since elevation tint alone isn't a strong enough separator there.
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
