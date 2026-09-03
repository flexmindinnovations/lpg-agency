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
        padding: const EdgeInsets.all(16),
        children: [
          if (pending == 0 && issues.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 64),
              child: LpgEmptyState(
                message: "Everything's synced.",
                icon: Icons.cloud_done_outlined,
              ),
            ),
          if (pending > 0) ...[
            _PendingCard(
              count: pending,
              onSyncNow: () {
                ref.read(syncCoordinatorProvider).syncNow(ignoreBackoff: true);
              },
            ),
            const SizedBox(height: 16),
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
            const SizedBox(height: 12),
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
    ref.invalidate(pendingCashHandoverProvider);
  }
}

class _PendingCard extends StatelessWidget {
  const _PendingCard({required this.count, required this.onSyncNow});

  final int count;
  final VoidCallback onSyncNow;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.sync, size: 18, color: colors.textSecondary),
              const SizedBox(width: 8),
              Text(
                '$count change${count == 1 ? '' : 's'} waiting to sync',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          LpgButton(
            label: 'Sync now',
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
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final isConflict = op.status == 'conflict';

    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  _label(op),
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colors.textPrimary,
                  ),
                ),
              ),
              LpgStatusBadge(
                label: isConflict ? 'REJECTED' : 'FAILED',
                severity: isConflict
                    ? LpgStatusSeverity.warning
                    : LpgStatusSeverity.danger,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            isConflict
                ? 'The office already updated this. Their version is the '
                      'correct one — discard your change.'
                : (op.errorMessage ?? 'Something went wrong.'),
            style: theme.textTheme.bodySmall?.copyWith(
              color: colors.textSecondary,
            ),
          ),
          const SizedBox(height: 12),
          if (isConflict)
            LpgButton(
              label: 'Acknowledge & discard',
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
                    expand: true,
                    onPressed: onRetry,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: LpgButton(
                    label: 'Discard',
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
