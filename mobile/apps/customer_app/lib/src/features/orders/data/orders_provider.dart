import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

/// Provides the current customer's list of orders.
final ordersProvider = FutureProvider<List<OrderResponse>>((ref) async {
  final api = ref.watch(orderApiProvider);
  final authController = ref.watch(authControllerProvider);

  if (authController.state.status == AuthStatus.authenticated &&
      authController.state.principal != null) {
    final result = await api.getMyOrders();
    return result.when(
      onSuccess: (data) => data.items,
      onFailure: (failure) => throw Exception(failure.message),
    );
  }

  return [];
});

/// Provides a single order by its ID.
final orderDetailProvider = FutureProvider.family<OrderResponse, String>((
  ref,
  id,
) async {
  final api = ref.watch(orderApiProvider);
  final result = await api.getOrder(id);
  return result.when(
    onSuccess: (data) => data,
    onFailure: (failure) => throw Exception(failure.message),
  );
});

/// Live `order.status_changed` events for one order, over the backend's
/// `/ws` (`RealtimeClient.subscribeToOrder`). `autoDispose` so the
/// underlying subscription (and the intent it registers on the shared
/// socket) goes away once no screen is watching this order anymore --
/// there's no explicit "unsubscribe" on `RealtimeClient` itself, this is
/// how a per-order subscription's lifetime is actually bounded.
final orderRealtimeProvider = StreamProvider.autoDispose
    .family<Map<String, dynamic>, String>((ref, orderId) {
      final client = ref.watch(realtimeClientProvider);
      return client.subscribeToOrder(orderId);
    });
