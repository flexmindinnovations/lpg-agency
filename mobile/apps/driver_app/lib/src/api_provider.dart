import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The Driver App's shared [ApiClient]. `main()` wires the real instance
/// (auth token, refresh, session-expiry callback) and overrides this before
/// the first frame — the same pattern as [localDatabaseProvider]. The
/// default fails loudly if that override is missed.
final apiClientProvider = Provider<ApiClient>(
  (ref) => throw UnimplementedError(
    'apiClientProvider must be overridden in main() with the wired ApiClient.',
  ),
);

/// The Driver App's slice of the `/routes/*` API — the active route and
/// live-location reporting.
final routeApiProvider = Provider<RouteApi>(
  (ref) => RouteApi(ref.watch(apiClientProvider).dio),
);

/// The `/orders/*` API — used by the Driver App for the per-stop delivery
/// workflow (view, depart, record delivery, failed delivery).
final orderApiProvider = Provider<OrderApi>(
  (ref) => OrderApi(ref.watch(apiClientProvider).dio),
);

/// The `/drivers/*` API — the Profile tab's `GET /drivers/me`.
final driverApiProvider = Provider<DriverApi>(
  (ref) => DriverApi(ref.watch(apiClientProvider).dio),
);
