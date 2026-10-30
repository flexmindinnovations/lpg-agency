import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../providers.dart';
import '../data/notifications_provider.dart';

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  Future<void> _handleTap(
    BuildContext context,
    WidgetRef ref,
    NotificationResponse item,
  ) async {
    if (!item.isRead) {
      // Fire-and-forget: don't block navigation on this, and a failure
      // here shouldn't stop the customer from opening what they tapped.
      // Invalidate afterwards regardless, so the unread dot/badge catch up
      // next time this list or the dashboard bell is looked at.
      unawaited(
        ref.read(notificationApiProvider).markRead(item.id).then((_) {
          ref.invalidate(notificationsProvider);
          ref.invalidate(unreadNotificationCountProvider);
        }),
      );
    }

    // Only "order" reference notifications are produced by the backend
    // today (notification_jobs.py) -- nothing else to route to yet.
    if (item.referenceType == 'order' && item.referenceId != null) {
      if (context.mounted) {
        context.push('/orders/${item.referenceId}');
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notificationsAsync = ref.watch(notificationsProvider);
    final colors = context.lpgColors;

    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: notificationsAsync.when(
        loading: () => const LpgSkeletonList(),
        error: (err, stack) => LpgErrorState(
          message: 'Failed to load notifications',
          onRetry: () => ref.refresh(notificationsProvider),
        ),
        data: (notifications) {
          if (notifications.isEmpty) {
            return const LpgEmptyState(
              title: 'All caught up',
              message: 'No notifications yet',
              icon: LpgIcons.notificationsOff,
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(notificationsProvider.future),
            child: ListView(
              padding: LpgSpacing.page,
              children: [
                LpgGroupedList(
                  children: [
                    for (final item in notifications)
                      // Unread rows sit on a faint tint so they stand out
                      // without relying on the dot alone.
                      ColoredBox(
                        color: item.isRead
                            ? Colors.transparent
                            : colors.actionPrimaryContainer.withValues(
                                alpha: 0.45,
                              ),
                        child: Builder(
                          builder: (context) {
                            final (
                              icon,
                              tone,
                            ) = switch (item.notificationType) {
                              'ORDER_UPDATE' => (
                                LpgIcons.orders,
                                LpgTone.primary,
                              ),
                              'PROMOTIONAL' => (
                                LpgIcons.announcement,
                                LpgTone.accent,
                              ),
                              'SYSTEM' => (LpgIcons.settings, LpgTone.neutral),
                              _ => (LpgIcons.notifications, LpgTone.info),
                            };
                            return LpgListTile(
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
                              onTap: () => _handleTap(context, ref, item),
                            );
                          },
                        ),
                      ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
