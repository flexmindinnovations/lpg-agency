import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../offline/cached_resource.dart';

/// One stop's order, by order id. `GET /orders/{id}`, cached so an already-
/// opened stop still renders offline. `autoDispose` — the stop detail screen
/// is the only reader.
final stopOrderProvider = FutureProvider.autoDispose
    .family<OrderResponse, String>((ref, orderId) async {
      final map = await ref
          .watch(cachedResourceProvider)
          .getMap('/api/v1/orders/$orderId', type: 'order', id: orderId);
      if (map == null) {
        throw Exception('This stop is not available offline.');
      }
      return OrderResponse.fromJson(map);
    });
