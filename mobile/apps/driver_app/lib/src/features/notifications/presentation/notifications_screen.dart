import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_provider.dart';
import '../data/notifications_provider.dart';

/// The Alerts tab: the driver's notification history. Tapping an item marks
/// it read and deep-links the same way the push does.
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  Future<void> _handleTap(
    BuildContext context,
    WidgetRef ref,
    NotificationResponse item,
  ) async {
    if (!item.isRead) {
      // Fire-and-forget — don't block navigation, and a failed mark-read
      // shouldn't stop the driver opening what they tapped.
      unawaited(
        ref.read(notificationApiProvider).markRead(item.id).then((_) {
          ref.invalidate(driverNotificationsProvider);
          ref.invalidate(unreadNotificationCountProvider);
        }),
      );
    }

    if (item.referenceType == 'order' && item.referenceId != null) {
      if (context.mounted) {
        context.goNamed('stop', pathParameters: {'orderId': item.referenceId!});
      }
    } else if (item.referenceType == 'route') {
      if (context.mounted) context.go('/');
    }
  }

  Future<void> _markAllRead(WidgetRef ref) async {
    await ref.read(notificationApiProvider).markAllRead();
    ref.invalidate(driverNotificationsProvider);
    ref.invalidate(unreadNotificationCountProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final async = ref.watch(driverNotificationsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        actions: [
          if (async.value?.any((n) => !n.isRead) ?? false)
            TextButton(
              onPressed: () => _markAllRead(ref),
              child: const Text('Mark all read'),
            ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Could not load your alerts.\n$err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.invalidate(driverNotificationsProvider),
        ),
        data: (items) {
          if (items.isEmpty) {
            return const LpgEmptyState(
              message: 'No alerts yet.',
              icon: Icons.notifications_none_outlined,
            );
          }
          return RefreshIndicator(
            onRefresh: () => ref.refresh(driverNotificationsProvider.future),
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: items.length,
              separatorBuilder: (_, _) => const SizedBox(height: 12),
              itemBuilder: (context, i) {
                final item = items[i];
                final d = item.createdAt;
                return LpgCard(
                  padding: EdgeInsets.zero,
                  onTap: () => _handleTap(context, ref, item),
                  child: LpgListTile(
                    leadingIcon: _iconFor(item.notificationType),
                    title: item.title,
                    subtitle: item.body,
                    trailing: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          '${d.year}-${_two(d.month)}-${_two(d.day)}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                        if (!item.isRead)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                color: colors.actionPrimary,
                                shape: BoxShape.circle,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

  static IconData _iconFor(String type) => switch (type) {
    'route_ready' => Icons.local_shipping_outlined,
    'driver_assigned' => Icons.add_location_alt_outlined,
    'stop_cancelled' => Icons.cancel_outlined,
    'delivery_confirmed' => Icons.check_circle_outline,
    _ => Icons.notifications_outlined,
  };

  static String _two(int v) => v.toString().padLeft(2, '0');
}
