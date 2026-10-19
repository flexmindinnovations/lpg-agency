import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../offline/offline_banner.dart';
import '../../../offline/sync_providers.dart';
import '../../delivery/data/active_route_provider.dart';
import '../../notifications/data/notifications_provider.dart';

/// The Driver App shell: a persistent bottom [LpgNavigationBar] across the
/// four tabs (Today / Deliveries / Alerts / Profile). Mirrors the Customer
/// App's `AppShell` — same edge-to-edge bar and high-contrast treatment.
///
/// It's the always-mounted widget, so it owns the Alerts-tab unread badge
/// and keeps the route current: both are refetched on app resume, when a
/// foreground push lands, and when a notification arrives over `/ws`.
class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  late final AppLifecycleListener _lifecycle;

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(onResume: _refresh);
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(pushMessagesProvider, (_, _) => _refresh());
    ref.listen(notificationsRealtimeProvider, (_, next) {
      if (next.hasValue) _refresh();
    });

    final unread = ref.watch(unreadNotificationCountProvider).value ?? 0;
    final syncIssues = ref.watch(syncIssuesProvider).value?.length ?? 0;

    return Scaffold(
      // The banner sits above the tab screens' own Scaffolds, so it has to
      // carry the top status-bar inset itself.
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            const OfflineBanner(),
            Expanded(child: widget.navigationShell),
          ],
        ),
      ),
      bottomNavigationBar: LpgNavigationBar(
        selectedIndex: widget.navigationShell.currentIndex,
        onDestinationSelected: _onTap,
        destinations: [
          const LpgNavDestination(
            icon: LpgIcons.today,
            selectedIcon: LpgIcons.todayFilled,
            label: 'Today',
          ),
          const LpgNavDestination(
            icon: LpgIcons.deliveries,
            selectedIcon: LpgIcons.deliveriesFilled,
            label: 'Deliveries',
          ),
          LpgNavDestination(
            icon: LpgIcons.notifications,
            selectedIcon: LpgIcons.notificationsFilled,
            label: 'Alerts',
            badgeCount: unread,
          ),
          // Sync issues badge the Profile tab — "something in the queue
          // needs you" (the Sync status screen is reached from Profile).
          LpgNavDestination(
            icon: LpgIcons.profile,
            selectedIcon: LpgIcons.profileFilled,
            label: 'Profile',
            badgeCount: syncIssues,
          ),
        ],
      ),
    );
  }

  /// A notification means something changed for this driver (new or
  /// cancelled stop, route ready): refresh the badge, the inbox and the route.
  void _refresh() {
    ref.invalidate(unreadNotificationCountProvider);
    ref.invalidate(driverNotificationsProvider);
    ref.invalidate(activeRouteProvider);
  }

  void _onTap(int index) {
    widget.navigationShell.goBranch(
      index,
      initialLocation: index == widget.navigationShell.currentIndex,
    );
    // Opening the Alerts tab is the moment to sync the badge.
    if (index == 2) ref.invalidate(unreadNotificationCountProvider);
  }
}
