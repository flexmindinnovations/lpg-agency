import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';

final dashboardSummaryProvider = FutureProvider<DashboardSummaryResponse>((ref) async {
  final adminApi = ref.watch(adminApiProvider);
  final result = await adminApi.getDashboardSummary();
  return switch (result) {
    Success(:final value) => value,
    FailureResult(:final failure) => throw Exception(failure.message),
  };
});

final operationsSnapshotProvider = FutureProvider<OperationsSnapshotResponse>((ref) async {
  final adminApi = ref.watch(adminApiProvider);
  final result = await adminApi.getOperationsSnapshot();
  return switch (result) {
    Success(:final value) => value,
    FailureResult(:final failure) => throw Exception(failure.message),
  };
});
