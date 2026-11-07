import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../customers/data/customers_provider.dart';
import '../data/complaints_provider.dart';
import 'complaint_presentation.dart';
import 'complaint_detail_screen.dart';

/// The status chips: label and the server's status value (`null` = all).
const _statusFilters = <(String, String?)>[
  ('All', null),
  ('Open', 'Open'),
  ('Assigned', 'Assigned'),
  ('In progress', 'InProgress'),
  ('Resolved', 'Resolved'),
  ('Rejected', 'Rejected'),
];

/// Every complaint the agency has, narrowed by status (and by one customer
/// when opened from their page). Safety and overdue ones say so on the row.
class ComplaintsScreen extends ConsumerStatefulWidget {
  const ComplaintsScreen({super.key, this.customerId, this.initialStatus});

  final String? customerId;
  final String? initialStatus;

  @override
  ConsumerState<ComplaintsScreen> createState() => _ComplaintsScreenState();
}

class _ComplaintsScreenState extends ConsumerState<ComplaintsScreen> {
  late String? _status = widget.initialStatus;
  int _pages = 1;

  ComplaintQuery get _query =>
      ComplaintQuery(status: _status, customerId: widget.customerId);

  void _refresh() => ref.invalidate(complaintsProvider);

  @override
  Widget build(BuildContext context) {
    final query = _query;
    final pages = [
      for (var p = 1; p <= _pages; p++)
        ref.watch(complaintsProvider((query, p))),
    ];
    final first = pages.first;
    final last = pages.last;
    final complaints = [for (final page in pages) ...?page.value?.items];
    final total = first.value?.total ?? 0;
    final hasMore =
        !last.isLoading && !last.hasError && complaints.length < total;
    final customerName = widget.customerId == null
        ? null
        : ref.watch(customerDetailProvider(widget.customerId!)).value?.fullName;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Complaints'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: _refresh,
          ),
        ],
      ),
      body: LpgMasterDetail(
        masterBuilder: (context, md) => Column(
          children: [
            if (widget.customerId != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  LpgSpacing.md,
                  LpgSpacing.sm,
                  LpgSpacing.md,
                  0,
                ),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: LpgFilterTag(
                    icon: LpgIcons.user,
                    label: customerName ?? 'This customer',
                    onRemove: () => context.go('/complaints'),
                    removeTooltip: 'Show every customer',
                  ),
                ),
              ),
            LpgChoiceChips<String?>.filterRow(
              options: {
                for (final (label, value) in _statusFilters) value: label,
              },
              selected: _status,
              onSelected: (value) => setState(() {
                _status = value;
                _pages = 1;
              }),
            ),
            Expanded(
              child: first.when(
                loading: () => const Padding(
                  padding: LpgSpacing.page,
                  child: LpgSkeletonList(itemCount: 5),
                ),
                error: (err, _) => LpgErrorState(
                  message: errorMessage(err),
                  onRetry: _refresh,
                ),
                data: (_) {
                  if (complaints.isEmpty) {
                    return LpgEmptyState(
                      icon: LpgIcons.complaint,
                      title: _status == null ? 'No complaints' : 'Nothing here',
                      message: _status == null
                          ? 'No customer has raised a complaint.'
                          : 'No complaints with this status.',
                    );
                  }
                  return RefreshIndicator(
                    onRefresh: () async {
                      _refresh();
                      await ref.read(complaintsProvider((query, 1)).future);
                    },
                    child: ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: LpgSpacing.page,
                      children: [
                        LpgGroupedList(
                          children: [
                            for (final c in complaints)
                              _ComplaintTile(complaint: c, md: md),
                          ],
                        ),
                        const SizedBox(height: LpgSpacing.md),
                        if (last.isLoading)
                          const Center(child: LpgLoadingIndicator())
                        else if (last.hasError)
                          LpgErrorState(
                            message: errorMessage(last.error!),
                            onRetry: _refresh,
                          )
                        else if (hasMore)
                          LpgButton(
                            label: 'Load more',
                            variant: LpgButtonVariant.secondary,
                            onPressed: () => setState(() => _pages++),
                          ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
        detailBuilder: (context, id) =>
            ComplaintDetailScreen(complaintId: id, embedded: true),
      ),
    );
  }
}

class _ComplaintTile extends StatelessWidget {
  const _ComplaintTile({required this.complaint, required this.md});

  final ComplaintResponse complaint;
  final LpgMasterDetailController md;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final overdue = complaint.isOverdue();
    final sla = slaLabel(complaint);
    final severity = complaintPrioritySeverity(complaint.priority);

    final tile = LpgListTile(
      leadingIcon: complaintCategoryIcon(complaint.category),
      leadingTone: complaint.isFinished ? LpgTone.neutral : severity.tone,
      title: complaintCategoryLabel(complaint.category),
      subtitle: [
        if (complaint.complaintNumber != null) complaint.complaintNumber!,
        complaint.customerName ?? 'Customer',
        ago(complaint.createdAt),
      ].join('  ·  '),
      trailing: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          LpgStatusBadge(
            label: humanizeStatus(complaint.status),
            severity: complaintStatusSeverity(complaint.status),
          ),
          if (sla != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                sla,
                style: text.labelSmall?.copyWith(
                  color: overdue ? colors.statusDanger : colors.textSecondary,
                ),
              ),
            ),
        ],
      ),
      showChevron: true,
      onTap: () {
        if (md.open(complaint.id)) return;
        context.pushNamed(
          'complaint_detail',
          pathParameters: {'complaintId': complaint.id},
        );
      },
    );
    return _selectable(context, md, complaint.id, tile);
  }
}

/// Highlights the row open in the tablet detail pane.
Widget _selectable(
  BuildContext context,
  LpgMasterDetailController md,
  String id,
  Widget tile,
) {
  if (!md.twoPane || md.selectedId != id) return tile;
  return ColoredBox(
    color: context.lpgColors.actionPrimaryContainer,
    child: tile,
  );
}
