import 'package:api_client/api_client.dart';
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
