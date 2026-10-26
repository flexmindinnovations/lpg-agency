import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

final dashboardSummaryProvider = FutureProvider<DashboardSummaryResponse>((ref) async {
  final adminApi = ref.watch(adminApiProvider);
  final result = await adminApi.getDashboardSummary();
  return unwrap(result);
});

final operationsSnapshotProvider = FutureProvider<OperationsSnapshotResponse>((ref) async {
  final adminApi = ref.watch(adminApiProvider);
  final result = await adminApi.getOperationsSnapshot();
  return unwrap(result);
});
