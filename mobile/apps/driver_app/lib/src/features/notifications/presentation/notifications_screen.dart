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
    final colors = context.lpgColors;
    final async = ref.watch(driverNotificationsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        actions: [
          if (async.value?.any((n) => !n.isRead) ?? false)
            TextButton.icon(
              onPressed: () => _markAllRead(ref),
              icon: const Icon(LpgIcons.allDone, size: LpgSizes.iconSm),
              label: const Text('Mark all read'),
            ),
        ],
      ),
      body: async.when(
        loading: () => const LpgSkeletonList(),
        error: (err, _) => LpgErrorState(
          message: 'Could not load your alerts.\n$err',
          onRetry: () => ref.invalidate(driverNotificationsProvider),
        ),
        data: (items) {
          if (items.isEmpty) {
            return const LpgEmptyState(
              title: 'All caught up',
              message: 'No alerts yet.',
              icon: LpgIcons.notificationsOff,
            );
          }
          return RefreshIndicator(
            onRefresh: () => ref.refresh(driverNotificationsProvider.future),
            child: ListView.separated(
              padding: LpgSpacing.page,
              itemCount: items.length,
              separatorBuilder: (_, _) => const SizedBox(height: LpgSpacing.sm),
              itemBuilder: (context, i) {
                final item = items[i];
                final (icon, tone) = _iconFor(item.notificationType);
                return LpgFadeSlideIn(
                  index: i,
                  child: LpgCard(
                    // Unread items sit on a tinted card so they stand out
                    // without relying on the dot alone.
                    variant: item.isRead
                        ? LpgCardVariant.outlined
                        : LpgCardVariant.tonal,
                    padding: EdgeInsets.zero,
                    child: LpgListTile(
                      onTap: () => _handleTap(context, ref, item),
                      leadingIcon: icon,
                      leadingTone: tone,
                      title: item.title,
                      subtitle: item.body,
                      trailing: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            LpgFormat.relative(item.createdAt),
                            style: context.lpgText.bodySmall,
                          ),
                          if (!item.isRead)
                            Padding(
                              padding: const EdgeInsets.only(
                                top: LpgSpacing.xs,
                              ),
                              child: Semantics(
                                label: 'Unread',
                                child: Container(
                                  width: LpgSpacing.sm,
                                  height: LpgSpacing.sm,
                                  decoration: BoxDecoration(
                                    color: colors.accent,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
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

  static (IconData, LpgTone) _iconFor(String type) => switch (type) {
    'route_ready' => (LpgIcons.truck, LpgTone.primary),
    'driver_assigned' => (LpgIcons.addLocation, LpgTone.info),
    'stop_cancelled' => (LpgIcons.cancel, LpgTone.danger),
    'delivery_confirmed' => (LpgIcons.success, LpgTone.success),
    _ => (LpgIcons.notifications, LpgTone.neutral),
  };
}
