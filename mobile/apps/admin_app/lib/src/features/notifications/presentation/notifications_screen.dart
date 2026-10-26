import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../data/notifications_provider.dart';

/// The Alerts tab: the office's notification history. Tapping an item marks
/// it read and opens the order it is about.
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  Future<void> _open(
    BuildContext context,
    WidgetRef ref,
    NotificationResponse item,
  ) async {
    if (!item.isRead) {
      unawaited(
        ref.read(notificationApiProvider).markRead(item.id).then((_) {
          ref.invalidate(adminNotificationsProvider);
          ref.invalidate(unreadNotificationCountProvider);
        }),
      );
    }
    final id = item.referenceId;
    if (item.referenceType == 'order' && id != null && context.mounted) {
      context.goNamed('order_detail', pathParameters: {'orderId': id});
    }
  }

  Future<void> _markAllRead(WidgetRef ref) async {
    await ref.read(notificationApiProvider).markAllRead();
    ref.invalidate(adminNotificationsProvider);
    ref.invalidate(unreadNotificationCountProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final async = ref.watch(adminNotificationsProvider);

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
          message: errorMessage(err),
          onRetry: () => ref.invalidate(adminNotificationsProvider),
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
            onRefresh: () => ref.refresh(adminNotificationsProvider.future),
            child: ListView.separated(
              padding: LpgSpacing.page,
              itemCount: items.length,
              separatorBuilder: (_, _) => const SizedBox(height: LpgSpacing.sm),
              itemBuilder: (context, i) {
                final item = items[i];
                return LpgCard(
                  // Unread items sit on a tinted card so they stand out
                  // without relying on the dot alone.
                  variant: item.isRead
                      ? LpgCardVariant.outlined
                      : LpgCardVariant.tonal,
                  padding: EdgeInsets.zero,
                  child: LpgListTile(
                    onTap: () => _open(context, ref, item),
                    leadingIcon: switch (item.referenceType) {
                      'order' => LpgIcons.orders,
                      'route' => LpgIcons.truck,
                      _ => LpgIcons.notifications,
                    },
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
                            padding: const EdgeInsets.only(top: LpgSpacing.xs),
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
                );
              },
            ),
          );
        },
      ),
    );
  }
}
