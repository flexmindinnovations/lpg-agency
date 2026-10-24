import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';

final pendingCashHandoversProvider = FutureProvider<List<CashHandoverRegisterEntryResponse>>((ref) async {
  final adminApi = ref.watch(adminApiProvider);
  final result = await adminApi.listCashHandovers(reviewStatus: 'pending');
  return switch (result) {
    Success(:final value) => value,
    FailureResult(:final failure) => throw Exception(failure.message),
  };
});
