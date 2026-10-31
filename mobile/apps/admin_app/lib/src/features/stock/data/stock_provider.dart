import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// The agency's godowns that are in use.
final stockGodownsProvider = FutureProvider<List<FleetWarehouse>>((ref) async {
  final all = unwrap(await ref.watch(fleetApiProvider).listWarehouses());
  return [
    for (final w in all)
      if (w.isActive) w,
  ];
});

/// What a godown holds, one line per cylinder type and status.
final godownBalanceProvider =
    FutureProvider.family<List<StockBalanceLine>, String>((
      ref,
      godownId,
    ) async {
      return unwrap(
        await ref
            .watch(fleetApiProvider)
            .getBalanceLines('warehouse', godownId),
      );
    });

/// Cylinder types at or below their reorder point, in every godown.
final reorderSignalsProvider = FutureProvider<List<ReorderSignal>>((ref) async {
  return unwrap(await ref.watch(fleetApiProvider).listReorderSignals());
});

/// The latest movements at a godown, newest first.
final godownMovementsProvider =
    FutureProvider.family<List<InventoryTransaction>, String>((
      ref,
      godownId,
    ) async {
      return unwrap(
        await ref
            .watch(fleetApiProvider)
            .listTransactions('warehouse', godownId, limit: 12),
      );
    });

/// Physical counts at a godown still waiting for someone to approve them.
final pendingCountsProvider =
    FutureProvider.family<List<ReconciliationRecord>, String>((
      ref,
      godownId,
    ) async {
      return unwrap(
        await ref
            .watch(fleetApiProvider)
            .listReconciliations('warehouse', godownId, state: 'pending'),
      );
    });

/// The moves the server allows between statuses.
final statusTransitionsProvider = FutureProvider<StatusTransitions>((
  ref,
) async {
  return unwrap(await ref.watch(fleetApiProvider).getStatusTransitions());
});

/// Certified scales in service at a godown, for logging a receipt sample.
/// A role that may not weigh gets an empty list rather than an error.
final receiptScalesProvider = FutureProvider.family<List<ScaleSummary>, String>(
  (ref, godownId) async {
    final result = await ref.watch(weighmentApiProvider).listActiveScales();
    return switch (result) {
      Success<List<ScaleSummary>>(:final value) => [
        for (final s in value)
          if (s.warehouseId == godownId) s,
      ],
      _ => const <ScaleSummary>[],
    };
  },
);

/// What a van is carrying, one line per cylinder type and status.
final vanStockProvider = FutureProvider.family<List<StockBalanceLine>, String>((
  ref,
  vanId,
) async {
  return unwrap(
    await ref.watch(fleetApiProvider).getBalanceLines('vehicle', vanId),
  );
});
