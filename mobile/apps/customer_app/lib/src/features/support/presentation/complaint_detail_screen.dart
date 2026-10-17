import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/complaints_provider.dart';
import 'complaint_presentation.dart';

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
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Scaffold(
      appBar: AppBar(title: const Text('Complaint Details')),
      body: complaintAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 3),
        error: (err, _) => LpgErrorState(
          message: 'Failed to load this complaint\n$err',
          onRetry: () => ref.refresh(complaintDetailProvider(complaintId)),
        ),
        data: (complaint) {
          final severity = complaintStatusSeverity(complaint.status);
          final priorityColor = switch (complaint.priority) {
            'Critical' => colors.statusDanger,
            'High' => colors.statusWarning,
            _ => colors.textSecondary,
          };

          final sections = <Widget>[
            LpgCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      LpgIconBox(icon: LpgIcons.complaint, tone: severity.tone),
                      const SizedBox(width: LpgSpacing.smd),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _humanize(complaint.category),
                              style: text.titleLarge,
                            ),
                            if (complaint.complaintNumber != null)
                              Text(
                                complaint.complaintNumber!,
                                style: text.bodySmall,
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: LpgSpacing.md),
                  LpgStatusBadge(
                    label: _humanize(complaint.status).toUpperCase(),
                    severity: severity,
                  ),
                  const SizedBox(height: LpgSpacing.sm),
                  LpgKeyValueRow(
                    icon: LpgIcons.flag,
                    label: 'Priority',
                    value: '${complaint.priority} priority',
                    valueColor: priorityColor,
                  ),
                  LpgKeyValueRow(
                    icon: LpgIcons.calendar,
                    label: 'Opened',
                    value: LpgFormat.date(complaint.createdAt),
                  ),
                  if (complaint.slaDueAt != null)
                    LpgKeyValueRow(
                      icon: LpgIcons.timer,
                      label: 'Expected resolution by',
                      value: LpgFormat.dateTime(complaint.slaDueAt!),
                    ),
                ],
              ),
            ),
            const LpgSectionHeader(title: 'Description'),
            LpgCard(child: Text(complaint.description, style: text.bodyLarge)),
            const LpgSectionHeader(title: 'Resolution'),
            if (complaint.resolution case final resolution?)
              LpgCard(
                variant: LpgCardVariant.tonal,
                tone: resolution.outcome == 'Rejected'
                    ? LpgTone.danger
                    : LpgTone.success,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LpgStatusBadge(
                      label: _humanize(resolution.outcome).toUpperCase(),
                      severity: resolution.outcome == 'Rejected'
                          ? LpgStatusSeverity.danger
                          : LpgStatusSeverity.success,
                    ),
                    const SizedBox(height: LpgSpacing.smd),
                    Text(resolution.resolutionNotes, style: text.bodyLarge),
                    const SizedBox(height: LpgSpacing.smd),
                    Text(
                      'Resolved on ${LpgFormat.date(resolution.resolvedAt)}',
                      style: text.bodySmall,
                    ),
                  ],
                ),
              )
            else
              const LpgBanner(
                icon: LpgIcons.pending,
                message:
                    "We're on it — you'll be notified as soon as this "
                    'complaint is resolved.',
              ),
          ];

          return ListView(
            padding: LpgSpacing.page,
            children: [
              for (var i = 0; i < sections.length; i++)
                LpgFadeSlideIn(index: i, child: sections[i]),
            ],
          );
        },
      ),
    );
  }
}
