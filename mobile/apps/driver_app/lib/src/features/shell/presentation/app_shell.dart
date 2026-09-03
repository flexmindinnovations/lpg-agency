import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../offline/offline_banner.dart';
import '../../../offline/sync_providers.dart';
import '../../notifications/data/notifications_provider.dart';

/// The Driver App shell: a persistent bottom `NavigationBar` across the four
/// tabs (Today / Deliveries / Alerts / Profile). Mirrors the Customer App's
/// `AppShell` — same edge-to-edge bar and high-contrast treatment.
///
/// It's the always-mounted widget, so it owns the Alerts-tab unread badge:
/// refetched on app resume and whenever a foreground push lands (no realtime
/// WebSocket — the push itself is the signal).
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
    _lifecycle = AppLifecycleListener(
      onResume: () => ref.invalidate(unreadNotificationCountProvider),
    );
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(pushMessagesProvider, (_, _) {
      ref.invalidate(unreadNotificationCountProvider);
      ref.invalidate(driverNotificationsProvider);
    });

    final colors = Theme.of(context).extension<LpgColors>()!;
    final unread = ref.watch(unreadNotificationCountProvider).value ?? 0;
    final syncIssues = ref.watch(syncIssuesProvider).value?.length ?? 0;

    Widget alertsIcon(IconData icon, Color color) => Badge(
      isLabelVisible: unread > 0,
      label: Text('$unread'),
      child: Icon(icon, color: color),
    );

    // A small dot (not a count) — "something in the queue needs you".
    Widget profileIcon(IconData icon, Color color) => Badge(
      isLabelVisible: syncIssues > 0,
      child: Icon(icon, color: color),
    );

    return Scaffold(
      body: Column(
        children: [
          const OfflineBanner(),
          Expanded(child: widget.navigationShell),
        ],
      ),
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
            selectedIndex: widget.navigationShell.currentIndex,
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
                icon: alertsIcon(
                  Icons.notifications_outlined,
                  colors.textSecondary,
                ),
                selectedIcon: alertsIcon(
                  Icons.notifications,
                  colors.actionPrimary,
                ),
                label: 'Alerts',
              ),
              NavigationDestination(
                icon: profileIcon(Icons.person_outline, colors.textSecondary),
                selectedIcon: profileIcon(Icons.person, colors.actionPrimary),
                label: 'Profile',
              ),
            ],
          ),
        ),
      ),
    );
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
