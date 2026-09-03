import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../offline/cached_resource.dart';

/// The driver's active route (or `null` when they have none). `GET
/// /routes/active`, cached so the route + its stops survive a signal dead
/// zone; a genuine `404` (route finished) evicts the cache rather than
/// resurrecting a stale one.
final activeRouteProvider = FutureProvider<RouteSummary?>((ref) async {
  final authController = ref.watch(authControllerProvider);
  if (authController.state.status != AuthStatus.authenticated) {
    return null;
  }

  final map = await ref
      .watch(cachedResourceProvider)
      .getMap(
        '/api/v1/routes/active',
        type: 'route_active',
        id: 'current',
        absentWhen: (e) => e.response?.statusCode == 404,
      );
  return map == null ? null : RouteSummary.fromJson(map);
});

/// The driver's finished routes (completed / reconciled / cancelled), newest
/// first — the delivery-history list on the Deliveries tab. Cached for
/// offline; capped at the most recent ~20, pagination is a follow-up.
final routeHistoryProvider = FutureProvider<List<RouteSummary>>((ref) async {
  final authController = ref.watch(authControllerProvider);
  if (authController.state.status != AuthStatus.authenticated) {
    return const [];
  }

  final map = await ref
      .watch(cachedResourceProvider)
      .getMap(
        '/api/v1/routes',
        type: 'route_history',
        id: 'current',
        queryParameters: {'page_size': 20},
      );

  final items = (map?['items'] as List<dynamic>? ?? const [])
      .map((e) => RouteSummary.fromJson(e as Map<String, dynamic>))
      .toList();
  const finished = {'completed', 'reconciled', 'cancelled'};
  return items.where((r) => finished.contains(r.status)).toList()
    ..sort((a, b) => (b.date ?? DateTime(0)).compareTo(a.date ?? DateTime(0)));
});
