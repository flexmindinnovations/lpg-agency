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
