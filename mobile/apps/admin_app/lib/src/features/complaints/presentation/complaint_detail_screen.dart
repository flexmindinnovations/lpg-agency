import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../api_result.dart';
import '../../../shared/metric_tile.dart';
import '../../dashboard/data/dashboard_providers.dart';
import '../data/complaints_provider.dart';
import 'assign_complaint_sheet.dart';
import 'complaint_presentation.dart';
import 'resolve_complaint_sheet.dart';

/// One complaint: who raised it and about which order, how long is left on its
/// deadline, who has it, what was done, and the two things staff do with it:
/// hand it to someone and resolve it.
class ComplaintDetailScreen extends ConsumerWidget {
  const ComplaintDetailScreen({super.key, required this.complaintId});

  final String complaintId;

  void _reload(WidgetRef ref) {
    ref.invalidate(complaintDetailProvider(complaintId));
    ref.invalidate(complaintsProvider);
    ref.invalidate(operationsSnapshotProvider);
  }

  Future<void> _assign(
    BuildContext context,
    WidgetRef ref,
    ComplaintResponse complaint,
  ) async {
    final done = await LpgFeedback.showSheet<bool>(
      context,
      title: complaint.assignments.isEmpty ? 'Assign' : 'Reassign',
      builder: (_) => AssignComplaintSheet(complaint: complaint),
    );
    if (done != true || !context.mounted) return;
    _reload(ref);
    LpgFeedback.showToast(
      context,
      'Complaint assigned.',
      tone: LpgTone.success,
    );
  }

  Future<void> _resolve(
    BuildContext context,
    WidgetRef ref,
    ComplaintResponse complaint,
  ) async {
    final done = await LpgFeedback.showSheet<bool>(
      context,
      title: 'Resolve complaint',
      builder: (_) => ResolveComplaintSheet(complaint: complaint),
    );
    if (done != true || !context.mounted) return;
    _reload(ref);
    LpgFeedback.showToast(
      context,
      'Complaint resolved.',
      tone: LpgTone.success,
    );
  }

  Future<void> _call(BuildContext context, String phone) async {
    if (!await launchUrl(Uri(scheme: 'tel', path: phone)) && context.mounted) {
      LpgFeedback.showToast(
        context,
        'Could not open the phone app.',
        tone: LpgTone.danger,
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(complaintDetailProvider(complaintId));

    return Scaffold(
      appBar: AppBar(
        title: Text(async.value?.complaintNumber ?? 'Complaint'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: () => _reload(ref),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgErrorState(
          message: errorMessage(err),
          onRetry: () => _reload(ref),
        ),
        data: (c) => _body(context, ref, c),
      ),
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, ComplaintResponse c) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final sla = slaLabel(c);
    final overdue = c.isOverdue();
    final safety = c.category == 'GasLeakSafety';
    final assignments = [...c.assignments]
      ..sort((a, b) => b.assignedAt.compareTo(a.assignedAt));

    return RefreshIndicator(
      onRefresh: () async {
        _reload(ref);
        await ref.read(complaintDetailProvider(complaintId).future);
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: LpgSpacing.page,
        children: [
          if (safety && !c.isFinished) ...[
            const LpgBanner(
              tone: LpgTone.danger,
              title: 'Safety issue',
              message:
                  'Gas leak or fire risk. Call the customer now and send the '
                  'emergency team if needed.',
            ),
            const SizedBox(height: LpgSpacing.md),
          ],
          LpgCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    LpgIconBox(
                      icon: complaintCategoryIcon(c.category),
                      tone: complaintPrioritySeverity(c.priority).tone,
                    ),
                    const SizedBox(width: LpgSpacing.md),
                    Expanded(
                      child: Text(
                        complaintCategoryLabel(c.category),
                        style: text.titleMedium,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: LpgSpacing.sm),
                Wrap(
                  spacing: LpgSpacing.xs,
                  runSpacing: LpgSpacing.xs,
                  children: [
                    LpgStatusBadge(
                      label: humanizeStatus(c.status),
                      severity: complaintStatusSeverity(c.status),
                    ),
                    LpgStatusBadge(
                      label: '${c.priority} priority',
                      severity: complaintPrioritySeverity(c.priority),
                    ),
                  ],
                ),
                const SizedBox(height: LpgSpacing.sm),
                Text(
                  'Raised ${LpgFormat.dateTime(c.createdAt)}',
                  style: text.bodySmall?.copyWith(color: colors.textSecondary),
                ),
                if (sla != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      sla,
                      style: text.titleSmall?.copyWith(
                        color: overdue
                            ? colors.statusDanger
                            : colors.textPrimary,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          if (c.customerPhone != null) ...[
            const SizedBox(height: LpgSpacing.md),
            LpgButton(
              label: 'Call ${c.customerName ?? 'customer'}',
              icon: LpgIcons.call,
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: () => _call(context, c.customerPhone!),
            ),
          ],
          const SectionHeading('What the customer said', topGap: LpgSpacing.lg),
          LpgCard(child: Text(c.description, style: text.bodyLarge)),
          const SectionHeading('About', topGap: LpgSpacing.lg),
          LpgGroupedList(
            children: [
              LpgListTile(
                leadingIcon: LpgIcons.user,
                title: c.customerName ?? 'Customer',
                subtitle: [?c.consumerNumber, ?c.customerPhone].join('  ·  '),
                showChevron: true,
                onTap: () => context.pushNamed(
                  'customer_detail',
                  pathParameters: {'customerId': c.customerId},
                ),
              ),
              if (c.orderId != null)
                LpgListTile(
                  leadingIcon: LpgIcons.orders,
                  title: 'Order ${c.orderNumber ?? ''}'.trim(),
                  subtitle: 'The order this is about',
                  showChevron: true,
                  onTap: () => context.goNamed(
                    'order_detail',
                    pathParameters: {'orderId': c.orderId!},
                  ),
                ),
              LpgListTile(
                leadingIcon: LpgIcons.badge,
                leadingTone: c.assigneeName == null
                    ? LpgTone.warning
                    : LpgTone.primary,
                title: c.assigneeName ?? 'Not assigned yet',
                subtitle: 'Handling this complaint',
              ),
            ],
          ),
          if (c.resolution != null) ...[
            const SectionHeading('Outcome', topGap: LpgSpacing.lg),
            LpgCard(
              variant: LpgCardVariant.tonal,
              tone: c.resolution!.outcome == 'Rejected'
                  ? LpgTone.danger
                  : LpgTone.success,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(c.resolution!.outcome, style: text.titleSmall),
                  const SizedBox(height: LpgSpacing.xs),
                  Text(c.resolution!.resolutionNotes, style: text.bodyMedium),
                  const SizedBox(height: LpgSpacing.xs),
                  Text(
                    LpgFormat.dateTime(c.resolution!.resolvedAt),
                    style: text.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (assignments.isNotEmpty) ...[
            const SectionHeading('History', topGap: LpgSpacing.lg),
            LpgGroupedList(
              children: [
                for (final a in assignments)
                  LpgListTile(
                    leadingIcon: LpgIcons.user,
                    leadingTone: LpgTone.neutral,
                    title:
                        'Assigned to ${a.assignedToName ?? 'a staff member'}',
                    subtitle: LpgFormat.dateTime(a.assignedAt),
                  ),
              ],
            ),
          ],
          if (!c.isFinished) ...[
            const SizedBox(height: LpgSpacing.lg),
            LpgButton(
              label: 'Resolve',
              icon: LpgIcons.check,
              expand: true,
              onPressed: () => _resolve(context, ref, c),
            ),
            const SizedBox(height: LpgSpacing.sm),
            LpgButton(
              label: c.assignments.isEmpty ? 'Assign to someone' : 'Reassign',
              icon: LpgIcons.user,
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: () => _assign(context, ref, c),
            ),
          ],
          const SizedBox(height: LpgSpacing.xl),
        ],
      ),
    );
  }
}
