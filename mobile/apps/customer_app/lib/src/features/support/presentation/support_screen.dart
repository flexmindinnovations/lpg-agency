import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../data/complaints_provider.dart';

class SupportScreen extends ConsumerWidget {
  const SupportScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final complaintsAsync = ref.watch(complaintsProvider);
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Support Center',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Help Header
          Padding(
            padding: const EdgeInsets.all(24.0),
            child: LpgCard(
              child: Column(
                children: [
                  const Icon(Icons.support_agent, size: 48),
                  const SizedBox(height: 16),
                  Text(
                    'How can we help you?',
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Our support team is available 24/7 for your assistance.',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 24),
                  LpgButton(
                    label: 'Raise a Complaint',
                    onPressed: () {
                      // TODO: Navigate to raise complaint screen
                    },
                    expand: true,
                  ),
                ],
              ),
            ),
          ),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24.0),
            child: Text(
              'Your Recent Tickets',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
                color: colors.textPrimary,
              ),
            ),
          ),

          const SizedBox(height: 16),

          Expanded(
            child: complaintsAsync.when(
              loading: () => const Center(child: LpgLoadingIndicator()),
              error: (err, stack) => LpgEmptyState(
                message: 'Failed to load tickets',
                icon: Icons.error_outline,
                actionLabel: 'Retry',
                onAction: () => ref.refresh(complaintsProvider),
              ),
              data: (complaints) {
                if (complaints.isEmpty) {
                  return const LpgEmptyState(
                    message: 'No complaints raised yet.',
                    icon: Icons.history,
                  );
                }

                return RefreshIndicator(
                  onRefresh: () async => ref.refresh(complaintsProvider.future),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 24,
                      vertical: 24,
                    ),
                    itemCount: complaints.length,
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                    itemBuilder: (context, index) {
                      final item = complaints[index];
                      final severity = switch (item.status) {
                        'Resolved' || 'Closed' => LpgStatusSeverity.success,
                        'InProgress' || 'Assigned' => LpgStatusSeverity.warning,
                        'Open' => LpgStatusSeverity.info,
                        'Rejected' => LpgStatusSeverity.danger,
                        _ => LpgStatusSeverity.neutral,
                      };

                      return LpgCard(
                        padding: EdgeInsets.zero,
                        child: LpgListTile(
                          title: item.category,
                          subtitle:
                              'Opened on ${DateFormat('MMM dd, yyyy').format(item.createdAt)}',
                          trailing: LpgStatusBadge(
                            label: item.status.toUpperCase(),
                            severity: severity,
                          ),
                          onTap: () {
                            // TODO: Navigate to complaint detail
                          },
                        ),
                      );
                    },
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
