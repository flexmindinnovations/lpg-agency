import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../offline/cached_resource.dart';
import '../../../offline/pending_sync.dart';

/// One stop's order, by order id. `GET /orders/{id}`, cached so an already-
/// opened stop still renders offline. While a mutation for this order is
/// queued, the local cache (already moved optimistically) is authoritative —
/// skip the network refetch so a not-yet-synced transition isn't clobbered
/// by stale server data. `autoDispose` — the stop detail screen is the only
/// reader.
final stopOrderProvider = FutureProvider.autoDispose
    .family<OrderResponse, String>((ref, orderId) async {
      final reader = ref.watch(cachedResourceProvider);
      final pending =
          ref.watch(pendingSyncAggregatesProvider).value ?? const <String>{};

      final map = pending.contains(orderId)
          ? await reader.readCached('order', orderId)
          : await reader.getMap(
              '/api/v1/orders/$orderId',
              type: 'order',
              id: orderId,
            );
      if (map == null) {
        throw Exception('This stop is not available offline.');
      }
      return OrderResponse.fromJson(map);
    });
