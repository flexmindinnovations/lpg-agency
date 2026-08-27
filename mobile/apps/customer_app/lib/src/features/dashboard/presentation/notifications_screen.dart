import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../data/notifications_provider.dart';

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notificationsAsync = ref.watch(notificationsProvider);
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Notifications',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: notificationsAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, stack) => LpgEmptyState(
          message: 'Failed to load notifications',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(notificationsProvider),
        ),
        data: (notifications) {
          if (notifications.isEmpty) {
            return const LpgEmptyState(
              message: 'No notifications yet',
              icon: Icons.notifications_none_outlined,
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(notificationsProvider.future),
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: notifications.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final item = notifications[index];
                final icon = switch (item.notificationType) {
                  'ORDER_UPDATE' => Icons.receipt_long_outlined,
                  'PROMOTIONAL' => Icons.campaign_outlined,
                  'SYSTEM' => Icons.settings_suggest_outlined,
                  _ => Icons.notifications_outlined,
                };

                return LpgCard(
                  padding: EdgeInsets.zero,
                  child: LpgListTile(
                    leadingIcon: icon,
                    title: item.title,
                    subtitle: item.body,
                    trailing: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          DateFormat('MMM dd').format(item.createdAt),
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                        if (!item.isRead)
                          Padding(
                            padding: const EdgeInsets.only(top: 4.0),
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
                    onTap: () {
                      // TODO: Mark as read and navigate if reference exists
                    },
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
