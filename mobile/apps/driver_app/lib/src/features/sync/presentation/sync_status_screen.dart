import 'dart:convert';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';

import '../../../offline/sync_providers.dart';
import '../../cash_handover/data/cash_handover_provider.dart';
import '../../delivery/data/active_route_provider.dart';
import '../../delivery/data/stop_order_provider.dart';

/// The offline queue's health: how many changes are still syncing, plus the
/// ones that need the driver — `failed` (retries exhausted or a bad request)
/// and `conflict` (the office already moved on; the server wins).
class SyncStatusScreen extends ConsumerWidget {
  const SyncStatusScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pending = ref.watch(pendingSyncCountProvider).value ?? 0;
    final issues = ref.watch(syncIssuesProvider).value ?? const [];

    return Scaffold(
      appBar: AppBar(title: const Text('Sync status')),
      body: ListView(
        padding: LpgSpacing.page,
        children: [
          if (pending == 0 && issues.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: LpgSpacing.xxl),
              child: LpgEmptyState(
                title: 'All up to date',
                message: "Everything's synced.",
                icon: LpgIcons.synced,
                tone: LpgTone.success,
              ),
            ),
          if (pending > 0) ...[
            _PendingCard(
              count: pending,
              onSyncNow: () {
                ref.read(syncCoordinatorProvider).syncNow(ignoreBackoff: true);
              },
            ),
            const SizedBox(height: LpgSpacing.md),
          ],
          for (final op in issues) ...[
            _IssueCard(
              op: op,
              onRetry: () =>
                  ref.read(syncCoordinatorProvider).retryOperation(op.id),
              onDiscard: () {
                ref.read(syncCoordinatorProvider).discardOperation(op.id);
                _reconcile(ref);
              },
            ),
            const SizedBox(height: LpgSpacing.smd),
          ],
        ],
      ),
    );
  }

  /// After discarding a rejected op, the local optimistic state is wrong —
  /// drop the cached reads so everything reloads the server's truth.
  void _reconcile(WidgetRef ref) {
    ref.invalidate(activeRouteProvider);
    ref.invalidate(routeHistoryProvider);
    ref.invalidate(stopOrderProvider);
    ref.invalidate(routeCashHandoverProvider);
    ref.invalidate(pendingCashHandoversProvider);
  }
}

class _PendingCard extends StatelessWidget {
  const _PendingCard({required this.count, required this.onSyncNow});

  final int count;
  final VoidCallback onSyncNow;

  @override
  Widget build(BuildContext context) {
    return LpgCard(
      variant: LpgCardVariant.tonal,
      tone: LpgTone.warning,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const LpgIconBox(icon: LpgIcons.sync, tone: LpgTone.warning),
              const SizedBox(width: LpgSpacing.smd),
              Expanded(
                child: Text(
                  '$count change${count == 1 ? '' : 's'} waiting to sync',
                  style: context.lpgText.titleSmall,
                ),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.smd),
          LpgButton(
            label: 'Sync now',
            icon: LpgIcons.upload,
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: onSyncNow,
          ),
        ],
      ),
    );
  }
}

class _IssueCard extends StatelessWidget {
  const _IssueCard({
    required this.op,
    required this.onRetry,
    required this.onDiscard,
  });

  final SyncOperation op;
  final VoidCallback onRetry;
  final VoidCallback onDiscard;

  @override
  Widget build(BuildContext context) {
    final isConflict = op.status == 'conflict';
    final severity = isConflict
        ? LpgStatusSeverity.warning
        : LpgStatusSeverity.danger;

    return LpgCard(
      variant: LpgCardVariant.outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              LpgIconBox(
                icon: isConflict ? LpgIcons.warning : LpgIcons.syncProblem,
                tone: severity.tone,
              ),
              const SizedBox(width: LpgSpacing.smd),
              Expanded(
                child: Text(_label(op), style: context.lpgText.titleSmall),
              ),
              LpgStatusBadge(
                label: isConflict ? 'REJECTED' : 'FAILED',
                severity: severity,
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.smd),
          Text(
            isConflict
                ? 'The office already updated this. Their version is the '
                      'correct one — discard your change.'
                : (op.errorMessage ?? 'Something went wrong.'),
            style: context.lpgText.bodyMedium?.copyWith(
              color: context.lpgColors.textSecondary,
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          if (isConflict)
            LpgButton(
              label: 'Acknowledge & discard',
              icon: LpgIcons.check,
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: onDiscard,
            )
          else
            Row(
              children: [
                Expanded(
                  child: LpgButton(
                    label: 'Retry',
                    icon: LpgIcons.sync,
                    expand: true,
                    onPressed: onRetry,
                  ),
                ),
                const SizedBox(width: LpgSpacing.smd),
                Expanded(
                  child: LpgButton(
                    label: 'Discard',
                    icon: LpgIcons.delete,
                    variant: LpgButtonVariant.secondary,
                    expand: true,
                    onPressed: onDiscard,
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  static String _label(SyncOperation op) {
    final id = _aggregateId(op);
    final ref = id == null ? '' : ' · ${id.substring(0, 8).toUpperCase()}';
    return switch (op.type) {
      'order_depart' => 'Start delivery$ref',
      'order_deliver' => 'Record delivery$ref',
      'order_failed_delivery' => 'Failed delivery$ref',
      'order_reschedule' => 'Reschedule$ref',
      'cash_handover_declare' => 'Cash handover$ref',
      _ => op.type,
    };
  }

  static String? _aggregateId(SyncOperation op) {
    try {
      final id =
          (jsonDecode(op.payload) as Map<String, dynamic>)['aggregateId'];
      return id is String ? id : null;
    } catch (_) {
      return null;
    }
  }
}
