import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';

/// Provides the tenant's active cylinder types, for order placement's
/// cylinder-type picker. Filters out inactive types here rather than
/// asking every caller to repeat the same `.where()`.
final cylinderTypesProvider = FutureProvider<List<CylinderTypeResponse>>((
  ref,
) async {
  final api = ref.watch(cylinderTypeApiProvider);
  final result = await api.list();
  return result.when(
    onSuccess: (data) => data.where((t) => t.isActive).toList(),
    onFailure: (failure) => throw Exception(failure.message),
  );
});
