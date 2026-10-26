import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

final pendingCashHandoversProvider = FutureProvider<List<CashHandoverRegisterEntryResponse>>((ref) async {
  final adminApi = ref.watch(adminApiProvider);
  final result = await adminApi.listCashHandovers(reviewStatus: 'pending');
  return unwrap(result);
});
