import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_provider.dart';
import '../../../offline/cached_resource.dart';
import '../../../offline/pending_sync.dart';
import '../../delivery/data/active_route_provider.dart';

/// The cash-reconciliation view for one route (`GET /cash-handovers/for-route
/// /{id}`), cached so the screen loads at the end of a route even in a dead
/// zone. While a declaration for this route is queued the cached view is
/// authoritative (skip the refetch); once it syncs, the pending set changes,
/// this rebuilds and the real receipt comes back. `autoDispose`.
final routeCashHandoverProvider = FutureProvider.autoDispose
    .family<RouteCashHandover, String>((ref, routeId) async {
      final reader = ref.watch(cachedResourceProvider);
      final pending =
          ref.watch(pendingSyncAggregatesProvider).value ?? const <String>{};

      final map = pending.contains(routeId)
          ? await reader.readCached('route_cash', routeId)
          : await reader.getMap(
              '/api/v1/cash-handovers/for-route/$routeId',
              type: 'route_cash',
              id: routeId,
            );
      if (map == null) {
        throw Exception('This route is not available offline.');
      }
      return RouteCashHandover.fromJson(map);
    });

/// Every finished route whose collected cash is still undeclared, newest
/// first. Drives the "reconcile your cash" nudges on Today and the CASH
/// PENDING badges in Deliveries.
///
/// All completed routes are checked, not just the latest: a later cash-free
/// route used to hide an earlier route's undeclared money (DR-01). A route
/// that collected no cash is never nudged — there is nothing to hand over
/// (DR-10). A route whose check fails is skipped; a nudge that can't load is
/// simply no nudge.
final pendingCashHandoversProvider =
    FutureProvider.autoDispose<List<RouteCashHandover>>((ref) async {
      final history = await ref.watch(routeHistoryProvider.future);
      final api = ref.watch(cashHandoverApiProvider);
      final completed = [
        for (final route in history)
          if (route.status == 'completed') route,
      ];
      final views = await Future.wait(
        completed.map((route) async {
          final result = await api.getForRoute(route.id);
          return result.when(onSuccess: (view) => view, onFailure: (_) => null);
        }),
      );
      return [
        for (final view in views)
          if (view != null && view.needsDeclaring) view,
      ];
    });

extension on RouteCashHandover {
  bool get needsDeclaring =>
      isPending && (expectedAmount > 0 || cashStopCount > 0);
}

/// Cash and UPI the signed-in driver is carrying that no handover covers yet
/// (`GET /cash-handovers/cash-in-hand/mine`). Online-only: a failed fetch is
/// simply no card, so Today still opens in a dead zone.
final myCashInHandProvider = FutureProvider.autoDispose<DriverCashInHand?>((
  ref,
) async {
  ref.watch(pendingSyncCountProvider);
  final result = await ref.watch(cashHandoverApiProvider).getMyCashInHand();
  if (result case Success(:final value)) {
    return value.drivers.isEmpty ? null : value.drivers.first;
  }
  return null;
});
