import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_provider.dart';
import '../../../auth_provider.dart';

/// The driver's active route (or `null` when they have none). Resolved from
/// the auth token by the backend's `GET /routes/active`.
final activeRouteProvider = FutureProvider<RouteSummary?>((ref) async {
  final authController = ref.watch(authControllerProvider);
  if (authController.state.status != AuthStatus.authenticated) {
    return null;
  }

  final result = await ref.watch(routeApiProvider).getMyActiveRoute();
  return result.when(
    onSuccess: (route) => route,
    onFailure: (failure) => throw Exception(failure.message),
  );
});

/// The driver's finished routes (completed / reconciled / cancelled), newest
/// first — the delivery-history list on the Deliveries tab. Capped at the
/// most recent ~20; pagination is a follow-up.
final routeHistoryProvider = FutureProvider<List<RouteSummary>>((ref) async {
  final authController = ref.watch(authControllerProvider);
  if (authController.state.status != AuthStatus.authenticated) {
    return const [];
  }

  final result = await ref.watch(routeApiProvider).listRoutes();
  return result.when(
    onSuccess: (routes) {
      const finished = {'completed', 'reconciled', 'cancelled'};
      final done = routes.where((r) => finished.contains(r.status)).toList()
        ..sort(
          (a, b) => (b.date ?? DateTime(0)).compareTo(a.date ?? DateTime(0)),
        );
      return done;
    },
    onFailure: (failure) => throw Exception(failure.message),
  );
});
