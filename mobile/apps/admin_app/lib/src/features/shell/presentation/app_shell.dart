import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:realtime/realtime.dart';

import '../../dashboard/data/dashboard_providers.dart';
import '../../dispatch/data/dispatch_provider.dart';
import '../../notifications/data/notifications_provider.dart';
import '../../orders/data/orders_provider.dart';

/// The always-mounted shell. It owns the Alerts-tab badge and listens to the
/// live `/ws` feed for the whole session: an order that changes anywhere
/// (the driver departs or delivers, another staff member confirms) refreshes
/// the order screens, and a new notification shows a toast and updates the
/// badge.
class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  void _onRealtime(
    BuildContext context,
    WidgetRef ref,
    Map<String, dynamic> m,
  ) {
    switch (m['type']) {
      case 'order.status_changed':
        _refreshOrders(ref);
        ref.invalidate(dashboardSummaryProvider);
        ref.invalidate(operationsSnapshotProvider);
      case 'notification.new':
        ref.invalidate(unreadNotificationCountProvider);
        ref.invalidate(adminNotificationsProvider);
        _showAlert(context, m);
      case reconnectedMessageType:
        // Anything may have changed while the socket was down.
        _refreshOrders(ref);
        ref.invalidate(dashboardSummaryProvider);
        ref.invalidate(operationsSnapshotProvider);
        ref.invalidate(unreadNotificationCountProvider);
        ref.invalidate(adminNotificationsProvider);
      default:
        // notification.read / notification.read_all
        ref.invalidate(unreadNotificationCountProvider);
        ref.invalidate(adminNotificationsProvider);
    }
  }

  void _refreshOrders(WidgetRef ref) {
    ref.invalidate(adminOrdersProvider);
    ref.invalidate(adminOrderDetailProvider);
    ref.invalidate(pendingCancellationProvider);
    ref.invalidate(orderHistoryProvider);
    ref.invalidate(activeTripsProvider);
    ref.invalidate(dispatchTripsProvider);
    ref.invalidate(ordersWaitingForTripProvider);
  }

  void _showAlert(BuildContext context, Map<String, dynamic> m) {
    final title = m['title'] as String?;
    final body = m['body'] as String?;
    if (title == null && body == null) return;
    final orderId = m['reference_type'] == 'order'
        ? m['reference_id'] as String?
        : null;
    LpgFeedback.showToast(
      context,
      [?title, ?body].join(' · '),
      tone: LpgTone.info,
      actionLabel: orderId == null ? null : 'View',
      onAction: orderId == null
          ? null
          : () => context.goNamed(
              'order_detail',
              pathParameters: {'orderId': orderId},
            ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(staffRealtimeProvider, (_, next) {
      final message = next.value;
      if (message != null) _onRealtime(context, ref, message);
    });

    ref.listen(pushMessagesProvider, (_, _) {
      ref.invalidate(unreadNotificationCountProvider);
      ref.invalidate(adminNotificationsProvider);
    });

    final unread = ref.watch(unreadNotificationCountProvider).value ?? 0;

    return LpgAdaptiveShell(
      body: navigationShell,
      selectedIndex: navigationShell.currentIndex,
      onDestinationSelected: _onTap,
      destinations: [
        const LpgNavDestination(
          icon: LpgIcons.home,
          selectedIcon: LpgIcons.homeFilled,
          label: 'Dashboard',
        ),
        const LpgNavDestination(
          icon: LpgIcons.orders,
          selectedIcon: LpgIcons.ordersFilled,
          label: 'Orders',
        ),
        const LpgNavDestination(
          icon: LpgIcons.truck,
          selectedIcon: LpgIcons.truckFilled,
          label: 'Dispatch',
        ),
        const LpgNavDestination(
          icon: LpgIcons.support,
          selectedIcon: LpgIcons.supportFilled,
          label: 'Approvals',
        ),
        LpgNavDestination(
          icon: LpgIcons.notifications,
          selectedIcon: LpgIcons.notificationsFilled,
          label: 'Alerts',
          badgeCount: unread,
        ),
        const LpgNavDestination(
          icon: LpgIcons.profile,
          selectedIcon: LpgIcons.profileFilled,
          label: 'Profile',
        ),
      ],
    );
  }

  void _onTap(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }
}
