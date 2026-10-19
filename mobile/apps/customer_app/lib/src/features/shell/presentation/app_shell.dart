import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../dashboard/data/notifications_provider.dart';
import '../../orders/data/orders_provider.dart';

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
      next.whenData((message) {
        ref.invalidate(notificationsProvider);
        ref.invalidate(unreadNotificationCountProvider);
        // Order notifications (confirmed, out for delivery, delivered, ...)
        // mean the order itself moved: refresh the Home and Orders lists,
        // and the order's own screen if it's open.
        if (message['reference_type'] == 'order') {
          ref.invalidate(ordersProvider);
          final orderId = message['reference_id'];
          if (orderId is String) ref.invalidate(orderDetailProvider(orderId));
        }
      });
    });

    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: LpgNavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (index) => _onTap(context, index),
        destinations: const [
          LpgNavDestination(
            icon: LpgIcons.home,
            selectedIcon: LpgIcons.homeFilled,
            label: 'Home',
          ),
          LpgNavDestination(
            icon: LpgIcons.orders,
            selectedIcon: LpgIcons.ordersFilled,
            label: 'Orders',
          ),
          LpgNavDestination(
            icon: LpgIcons.support,
            selectedIcon: LpgIcons.supportFilled,
            label: 'Support',
          ),
          LpgNavDestination(
            icon: LpgIcons.profile,
            selectedIcon: LpgIcons.profileFilled,
            label: 'Profile',
          ),
        ],
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
