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

/// The cylinder types this customer can book right now: active, priced for
/// them, and in stock at their branch. Order placement lists only these.
/// Auto-disposed so each visit to the order screen fetches fresh stock.
final orderableCylinderTypesProvider =
    FutureProvider.autoDispose<List<OrderableCylinderTypeResponse>>((
      ref,
    ) async {
      final api = ref.watch(cylinderTypeApiProvider);
      final result = await api.listOrderable();
      return result.when(
        onSuccess: (data) => data,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });
