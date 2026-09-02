import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_provider.dart';
import '../../delivery/data/active_route_provider.dart';

/// The cash-reconciliation view for one route (`GET /cash-handovers/for-route
/// /{id}`) — `autoDispose`, the handover screen is the only reader.
/// Invalidated after a successful declaration so it re-renders as the
/// receipt.
final routeCashHandoverProvider = FutureProvider.autoDispose
    .family<RouteCashHandover, String>((ref, routeId) async {
      final result = await ref.watch(cashHandoverApiProvider).getForRoute(routeId);
      return result.when(
        onSuccess: (view) => view,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });

/// The driver's most recent finished route whose cash still needs declaring,
/// or `null`. Drives the "reconcile your cash" nudge on the Today tab — a
/// nudge that can't load is simply no nudge.
final pendingCashHandoverProvider =
    FutureProvider.autoDispose<RouteCashHandover?>((ref) async {
      final history = await ref.watch(routeHistoryProvider.future);
      // `routeHistoryProvider` is already newest-first.
      RouteSummary? latestCompleted;
      for (final route in history) {
        if (route.status == 'completed') {
          latestCompleted = route;
          break;
        }
      }
      if (latestCompleted == null) return null;

      final result = await ref
          .watch(cashHandoverApiProvider)
          .getForRoute(latestCompleted.id);
      return result.when(
        onSuccess: (view) => view.isPending ? view : null,
        onFailure: (_) => null,
      );
    });
