import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../offline/cached_resource.dart';
import '../../../offline/pending_sync.dart';
import '../../delivery/data/active_route_provider.dart';

/// `cylinder_type_id -> name`, cache-first and best-effort (a missing name
/// falls back to a short id). The list is small and rarely changes.
final cylinderTypeNamesProvider = FutureProvider<Map<String, String>>((
  ref,
) async {
  final list = await ref
      .watch(cachedResourceProvider)
      .getList(
        '/api/v1/admin/cylinder-types',
        type: 'cylinder_types',
        id: 'all',
      );
  return {
    for (final entry in list.cast<Map<String, dynamic>>())
      entry['id'] as String: entry['name'] as String,
  };
});

/// One resolved manifest line for the van-load screen.
class VanLoadLine {
  const VanLoadLine({required this.label, required this.quantity});
  final String label;
  final int quantity;
}

/// The van-load view for the active route: the manifest (names resolved) and
/// whether the driver still has to confirm it.
class VanLoad {
  const VanLoad({required this.route, required this.lines});

  final RouteSummary route;
  final List<VanLoadLine> lines;

  bool get isConfirmed => route.loadConfirmedAt != null;
  int get totalCylinders => lines.fold(0, (sum, l) => sum + l.quantity);
}

/// The van-load view, `autoDispose.family` by route id. Reached only while
/// the route is the driver's active one, so it reads `activeRouteProvider`
/// (already cache-first) rather than a separate fetch.
final routeLoadProvider = FutureProvider.autoDispose.family<VanLoad, String>((
  ref,
  routeId,
) async {
  final route = await ref.watch(activeRouteProvider.future);
  if (route == null || route.id != routeId) {
    throw Exception('This route is no longer active.');
  }
  final names = await ref.watch(cylinderTypeNamesProvider.future);
  return VanLoad(
    route: route,
    lines: [
      for (final line in route.loadedLines)
        VanLoadLine(
          label:
              names[line.cylinderTypeId] ??
              line.cylinderTypeId.substring(0, 8).toUpperCase(),
          quantity: line.quantity,
        ),
    ],
  );
});

/// The active route iff the office has loaded it but the driver hasn't
/// confirmed — drives the Today "check your van load" nudge. Hidden the
/// moment a confirmation is queued.
final pendingLoadProvider = FutureProvider.autoDispose<RouteSummary?>((
  ref,
) async {
  final route = await ref.watch(activeRouteProvider.future);
  if (route == null || !route.isLoadPending) return null;
  final pending =
      ref.watch(pendingSyncAggregatesProvider).value ?? const <String>{};
  return pending.contains(route.id) ? null : route;
});
