import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

final tripProvider = FutureProvider.autoDispose.family<RouteSummary, String>(
  (ref, tripId) async =>
      unwrap(await ref.watch(routeApiProvider).getRoute(tripId)),
);

/// Load-out and other weighments logged against a trip. Roles without
/// access get an empty list.
final tripWeighmentsProvider = FutureProvider.autoDispose
    .family<List<WeighmentRecord>, String>((ref, tripId) async {
      final result = await ref.watch(weighmentApiProvider).listForRoute(tripId);
      return switch (result) {
        Success(:final value) => value,
        FailureResult() => const <WeighmentRecord>[],
      };
    });

/// What the driver owes for a trip and the handover declared for it, read
/// only. `null` when the caller may not see it. Declaring and reviewing
/// handovers stays with the cash handover flow.
final tripCashProvider = FutureProvider.autoDispose
    .family<RouteCashHandover?, String>((ref, tripId) async {
      final result = await ref
          .watch(cashHandoverApiProvider)
          .getForRoute(tripId);
      return switch (result) {
        Success(:final value) => value,
        FailureResult() => null,
      };
    });
