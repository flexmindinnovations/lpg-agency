import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'sync_providers.dart';

/// The set of aggregate ids (order ids, route ids) that have an unsynced
/// mutation in flight. A screen showing one of these treats its local
/// optimistic state as the source of truth — a "Pending sync" chip, and the
/// read providers skip the network refetch so a not-yet-synced transition
/// isn't clobbered by stale server data.
///
/// Derived from the queue's `payload.aggregateId`, which every driver op the
/// app enqueues carries.
final pendingSyncAggregatesProvider = StreamProvider<Set<String>>((ref) {
  return ref.watch(syncCoordinatorProvider).watchActive().map((ops) {
    final ids = <String>{};
    for (final op in ops) {
      try {
        final decoded = jsonDecode(op.payload) as Map<String, dynamic>;
        final id = decoded['aggregateId'];
        if (id is String) ids.add(id);
      } catch (_) {
        // A payload we can't read tells us nothing about an aggregate.
      }
    }
    return ids;
  });
});

/// `cylinder_type_id -> empties already queued for delivery`, summed across
/// every unsynced `order_deliver` op. The record-delivery screen adds the
/// current stop's figure on top to warn when the route would hand back more
/// empties than the van was loaded with. Best-effort: a synced delivery has
/// already cleared the server and no longer shows here.
final queuedEmptiesByTypeProvider = StreamProvider<Map<String, int>>((ref) {
  return ref.watch(syncCoordinatorProvider).watchActive().map((ops) {
    final totals = <String, int>{};
    for (final op in ops) {
      if (op.type != 'order_deliver') continue;
      try {
        final body =
            (jsonDecode(op.payload) as Map<String, dynamic>)['body']
                as Map<String, dynamic>?;
        for (final line
            in (body?['lines'] as List<dynamic>? ?? const [])
                .cast<Map<String, dynamic>>()) {
          final id = line['cylinder_type_id'] as String;
          totals[id] =
              (totals[id] ?? 0) +
              (line['quantity_collected_empty'] as num).toInt();
        }
      } catch (_) {
        // A payload we can't read tells us nothing about the empties.
      }
    }
    return totals;
  });
});
