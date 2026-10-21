import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/features/cash_handover/data/cash_handover_provider.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

RouteSummary _completed(String id, DateTime date) => RouteSummary(
  id: id,
  status: 'completed',
  driverId: 'driver-1',
  vehicleId: 'vehicle-1',
  date: date,
  stops: const [],
);

/// `/for-route/{id}` per route: what each completed route still owes.
class _ForRouteAdapter implements HttpClientAdapter {
  _ForRouteAdapter(this.byRoute);

  final Map<String, ({double expected, int cashStops, bool declared})> byRoute;

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    final id = options.path.split('/').last;
    final r = byRoute[id]!;
    return ResponseBody.fromString(
      jsonEncode({
        'route_id': id,
        'driver_id': 'drv-1',
        'route_status': 'completed',
        'route_date': '2026-10-20T00:00:00Z',
        'expected_amount': r.expected.toStringAsFixed(2),
        'cash_stop_count': r.cashStops,
        'handover': r.declared
            ? {
                'id': 'csh-$id',
                'handover_number': 'CSH0001',
                'driver_id': 'drv-1',
                'route_id': id,
                'expected_amount': '0.00',
                'actual_amount': '0.00',
                'shortfall': '0.00',
                'declared_by': 'u',
                'declared_at': '2026-10-20T00:00:00Z',
              }
            : null,
      }),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  test('nudges for every route with undeclared cash, never for ₹0 (DR-01, '
      'DR-10)', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
      ..httpClientAdapter = _ForRouteAdapter({
        // Newest first: a cash-free route, a ₹0 route, then the one that
        // actually holds the customer's money.
        'r-upi': (expected: 0, cashStops: 0, declared: false),
        'r-empty': (expected: 0, cashStops: 0, declared: false),
        'r-cash': (expected: 1811, cashStops: 1, declared: false),
        'r-done': (expected: 900, cashStops: 1, declared: true),
      });
    final container = ProviderContainer(
      overrides: [
        cashHandoverApiProvider.overrideWithValue(CashHandoverApi(dio)),
        routeHistoryProvider.overrideWith(
          (ref) async => [
            _completed('r-upi', DateTime(2026, 10, 21)),
            _completed('r-empty', DateTime(2026, 10, 21)),
            _completed('r-cash', DateTime(2026, 10, 20)),
            _completed('r-done', DateTime(2026, 10, 19)),
          ],
        ),
      ],
    );
    addTearDown(container.dispose);

    final pending = await container.read(pendingCashHandoversProvider.future);

    expect(pending.map((v) => v.routeId), ['r-cash']);
    expect(pending.single.expectedAmount, 1811);
  });
}
