import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../offline/cached_resource.dart';
import '../../../offline/pending_sync.dart';

/// The empties the driver may take back at one delivery, by order id: what the
/// customer was holding before it, per cylinder size. `GET /orders/{id}/empties`,
/// cached when the stop is opened so the delivery can be recorded offline.
///
/// `null` means the figures were never loaded on this phone. A loaded answer
/// is never empty: it lists every size on the order, even one at 0.
final heldEmptiesProvider = FutureProvider.autoDispose
    .family<List<HeldEmpties>?, String>((ref, orderId) async {
      // A queued delivery to the same customer changes the figures once sent.
      ref.watch(pendingSyncCountProvider);
      final list = await ref
          .watch(cachedResourceProvider)
          .getList(
            '/api/v1/orders/$orderId/empties',
            type: 'order_empties',
            id: orderId,
          );
      if (list.isEmpty) return null;
      return [
        for (final entry in list.cast<Map<String, dynamic>>())
          HeldEmpties.fromJson(entry),
      ];
    });
