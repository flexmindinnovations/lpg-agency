import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/notifications/data/notifications_provider.dart';

/// The app bar every top-level screen shares: the screen title, a search
/// shortcut and the alerts bell with its unread count. Screens add their own
/// [actions] before the two fixed ones.
class AdminAppBar extends ConsumerWidget implements PreferredSizeWidget {
  const AdminAppBar({
    super.key,
    required this.title,
    this.subtitle,
    this.actions = const [],
    this.showSearch = true,
    this.showAlerts = true,
  });

  final String title;
  final String? subtitle;
  final List<Widget> actions;
  final bool showSearch;
  final bool showAlerts;

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight + 4);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final unread = ref.watch(unreadNotificationCountProvider).value ?? 0;

    return AppBar(
      titleSpacing: LpgSpacing.md,
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(title, style: text.titleLarge),
          if (subtitle != null)
            Text(
              subtitle!,
              style: text.bodySmall?.copyWith(color: colors.textSecondary),
            ),
        ],
      ),
      actions: [
        ...actions,
        if (showSearch)
          IconButton(
            tooltip: 'Search',
            icon: const Icon(LpgIcons.search),
            onPressed: () => context.pushNamed('search'),
          ),
        if (showAlerts)
          Padding(
            padding: const EdgeInsets.only(right: LpgSpacing.xs),
            child: IconButton(
              tooltip: unread > 0 ? 'Alerts, $unread unread' : 'Alerts',
              icon: unread > 0
                  ? Badge(
                      label: Text(unread > 99 ? '99+' : '$unread'),
                      child: const Icon(LpgIcons.notifications),
                    )
                  : const Icon(LpgIcons.notifications),
              onPressed: () => context.pushNamed('alerts'),
            ),
          ),
      ],
    );
  }
}
