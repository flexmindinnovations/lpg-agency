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
///
/// `autoDispose` so every visit to an order refetches it: a cached copy kept
/// offering Cancel and Pay Online for an order that had since been
/// delivered and paid.
final orderDetailProvider = FutureProvider.autoDispose
    .family<OrderResponse, String>((ref, id) async {
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

/// The delivery code the customer reads out to the driver, while the order
/// is out for delivery; `null` otherwise. Shown in the app so a late or
/// lost SMS never strands the driver at the door (CA-04).
final deliveryCodeProvider = FutureProvider.autoDispose.family<String?, String>(
  (ref, orderId) async {
    final result = await ref.watch(orderApiProvider).getDeliveryCode(orderId);
    return result.when(
      onSuccess: (code) => code,
      onFailure: (failure) => throw Exception(failure.message),
    );
  },
);

/// The cancellation request waiting for a manager on this order, if any —
/// so the order screen shows "Cancellation requested" instead of offering
/// Cancel again (CA-07).
final pendingCancellationProvider = FutureProvider.autoDispose
    .family<PendingCancellationResponse?, String>((ref, orderId) async {
      final result = await ref
          .watch(orderApiProvider)
          .getPendingCancellation(orderId);
      return result.when(
        onSuccess: (request) => request,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });

/// The order's status history, oldest first — where a failed delivery's or
/// a cancellation's reason is recorded.
final orderHistoryProvider = FutureProvider.autoDispose
    .family<List<OrderStatusHistoryEntry>, String>((ref, orderId) async {
      final result = await ref
          .watch(orderApiProvider)
          .getStatusHistory(orderId);
      return result.when(
        onSuccess: (entries) => entries,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });
