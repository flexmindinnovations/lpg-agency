import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../data/complaints_provider.dart';

/// Splits a PascalCase category/status value from the backend (e.g.
/// `"LateDelivery"`, mirroring `ComplaintCategory`/`ComplaintStatus` in
/// `api_client`) into readable words ("Late Delivery").
String _humanize(String pascalCase) => pascalCase
    .replaceAllMapped(RegExp('(?<=[a-z])(?=[A-Z])'), (m) => ' ')
    .trim();

class ComplaintDetailScreen extends ConsumerWidget {
  const ComplaintDetailScreen({super.key, required this.complaintId});

  final String complaintId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final complaintAsync = ref.watch(complaintDetailProvider(complaintId));
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Complaint Details',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: complaintAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Failed to load this complaint\n$err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(complaintDetailProvider(complaintId)),
        ),
        data: (complaint) {
          final severity = switch (complaint.status) {
            'Resolved' || 'Closed' => LpgStatusSeverity.success,
            'InProgress' || 'Assigned' => LpgStatusSeverity.warning,
            'Open' => LpgStatusSeverity.info,
            'Rejected' => LpgStatusSeverity.danger,
            _ => LpgStatusSeverity.neutral,
          };
          final priorityColor = switch (complaint.priority) {
            'Critical' => colors.statusDanger,
            'High' => colors.statusWarning,
            _ => colors.textSecondary,
          };

          return ListView(
            padding: const EdgeInsets.all(24.0),
            children: [
              LpgCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            _humanize(complaint.category),
                            style: theme.textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: colors.textPrimary,
                            ),
                          ),
                        ),
                        LpgStatusBadge(
                          label: _humanize(complaint.status).toUpperCase(),
                          severity: severity,
                        ),
                      ],
                    ),
                    if (complaint.complaintNumber != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        complaint.complaintNumber!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colors.textSecondary,
                        ),
                      ),
                    ],
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Icon(
                          Icons.flag_outlined,
                          size: 16,
                          color: priorityColor,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          '${complaint.priority} priority',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: priorityColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Icon(
                          Icons.calendar_today_outlined,
                          size: 16,
                          color: colors.textSecondary,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          DateFormat(
                            'MMM dd, yyyy',
                          ).format(complaint.createdAt),
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),
              Text(
                'Description',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              LpgCard(
                child: Text(
                  complaint.description,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.textPrimary,
                  ),
                ),
              ),

              if (complaint.slaDueAt != null) ...[
                const SizedBox(height: 24),
                LpgListTile(
                  leadingIcon: Icons.timer_outlined,
                  title: 'Expected resolution by',
                  subtitle: DateFormat(
                    'MMM dd, yyyy • hh:mm a',
                  ).format(complaint.slaDueAt!),
                ),
              ],

              const SizedBox(height: 24),
              Text(
                'Resolution',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              if (complaint.resolution case final resolution?)
                LpgCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      LpgStatusBadge(
                        label: _humanize(resolution.outcome).toUpperCase(),
                        severity: resolution.outcome == 'Rejected'
                            ? LpgStatusSeverity.danger
                            : LpgStatusSeverity.success,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        resolution.resolutionNotes,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: colors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Resolved on ${DateFormat('MMM dd, yyyy').format(resolution.resolvedAt)}',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                )
              else
                LpgCard(
                  child: Row(
                    children: [
                      Icon(Icons.hourglass_empty, color: colors.textSecondary),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Text(
                          "We're on it — you'll be notified as soon as this "
                          'complaint is resolved.',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }
}
