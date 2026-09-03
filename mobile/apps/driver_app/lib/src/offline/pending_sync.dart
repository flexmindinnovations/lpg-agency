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
