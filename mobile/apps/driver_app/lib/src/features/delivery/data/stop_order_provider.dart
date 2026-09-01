import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_provider.dart';

/// One stop's order, by order id. `autoDispose` — the stop detail screen is
/// the only reader.
final stopOrderProvider = FutureProvider.autoDispose
    .family<OrderResponse, String>((ref, orderId) async {
      final result = await ref.watch(orderApiProvider).getOrder(orderId);
      return result.when(
        onSuccess: (order) => order,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });
