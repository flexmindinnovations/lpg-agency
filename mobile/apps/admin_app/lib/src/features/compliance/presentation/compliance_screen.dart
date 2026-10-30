import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../shared/metric_tile.dart';
import '../../orders/data/orders_provider.dart';
import '../data/compliance_provider.dart';
import 'compliance_document_sheet.dart';
import 'compliance_presentation.dart';

/// Every licence, certificate and policy that has lapsed or lapses within 90
/// days, worst first, for drivers, vans, godowns and the agency itself. Open
/// one to see it and to renew it.
class ComplianceScreen extends ConsumerWidget {
  const ComplianceScreen({super.key});

  void _reload(WidgetRef ref) {
    ref.invalidate(complianceDocumentsProvider);
    ref.invalidate(complianceDueCountProvider);
    ref.invalidate(fleetProvider);
  }

  Future<void> _open(
    BuildContext context,
    WidgetRef ref,
    ComplianceDocument doc,
    FleetData? fleet,
  ) async {
    final renewed = await LpgFeedback.showSheet<ComplianceDocument>(
      context,
      title: complianceDocTypeLabel(doc.docType),
      builder: (_) => ComplianceDocumentSheet(
        document: doc,
        ownerName: complianceOwnerName(doc, fleet),
      ),
    );
    if (renewed == null || !context.mounted) return;
    _reload(ref);
    LpgFeedback.showToast(
      context,
      '${complianceDocTypeLabel(doc.docType)} renewed. It now needs verifying.',
      tone: LpgTone.success,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docs = ref.watch(complianceDocumentsProvider);
    final fleet = ref.watch(fleetProvider).value;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Licences and papers'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: () => _reload(ref),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          _reload(ref);
          await ref.read(complianceDocumentsProvider.future);
        },
        child: docs.when(
          loading: () => const LpgSkeletonList(itemCount: 5),
          error: (err, _) => ListView(
            children: [
              LpgErrorState(
                message: errorMessage(err),
                onRetry: () => _reload(ref),
              ),
            ],
          ),
          data: (list) {
            final grouped = groupByUrgency(list);
            final total = grouped.values.fold<int>(0, (n, l) => n + l.length);
            if (total == 0) {
              return ListView(
                children: const [
                  LpgEmptyState(
                    icon: LpgIcons.allDone,
                    tone: LpgTone.success,
                    title: 'Everything is in date',
                    message:
                        'No licence or paper has lapsed or lapses in the next 90 days.',
                  ),
                ],
              );
            }
            final firstShown = Urgency.values.firstWhere(
              (u) => grouped[u]!.isNotEmpty,
            );
            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: LpgSpacing.page,
              children: [
                for (final urgency in Urgency.values)
                  if (grouped[urgency]!.isNotEmpty) ...[
                    SectionHeading(
                      '${urgency.heading} (${grouped[urgency]!.length})',
                      topGap: urgency == firstShown ? 0 : LpgSpacing.lg,
                    ),
                    LpgGroupedList(
                      children: [
                        for (final d in grouped[urgency]!)
                          _DocumentTile(
                            doc: d,
                            fleet: fleet,
                            onTap: () => _open(context, ref, d, fleet),
                          ),
                      ],
                    ),
                  ],
                const SizedBox(height: LpgSpacing.xl),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _DocumentTile extends StatelessWidget {
  const _DocumentTile({
    required this.doc,
    required this.fleet,
    required this.onTap,
  });

  final ComplianceDocument doc;
  final FleetData? fleet;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final days = doc.daysLeft()!;
    final tone = urgencyFor(days).tone;

    return LpgListTile(
      leadingIcon: complianceOwnerIcon(doc.ownerType),
      leadingTone: tone,
      title: complianceDocTypeLabel(doc.docType),
      subtitle:
          '${complianceOwnerName(doc, fleet)} · ${LpgFormat.shortDate(doc.expiryDate!)}',
      trailing: Text(
        dueShort(days),
        style: text.titleSmall?.copyWith(color: tone.foreground(colors)),
      ),
      showChevron: true,
      onTap: onTap,
    );
  }
}
