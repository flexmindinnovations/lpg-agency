import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';

/// Online payment attempts for one order, newest first.
final orderPaymentsProvider = FutureProvider.autoDispose
    .family<List<OnlinePaymentResponse>, String>((ref, orderId) async {
      final result = await ref
          .watch(paymentApiProvider)
          .listOrderPayments(orderId);
      return result.when(
        onSuccess: (items) => items,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });

/// Whether "Pay Online" can be offered at all. `false` only when the server
/// says no gateway is configured (CA-17); if the check itself fails the
/// button stays, and a failed payment start explains itself in place.
final onlinePaymentAvailableProvider = FutureProvider<bool>((ref) async {
  final result = await ref.watch(paymentApiProvider).isAvailable();
  return result.when(
    onSuccess: (available) => available,
    onFailure: (_) => true,
  );
});
