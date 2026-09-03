import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

Map<String, dynamic> _handoverJson({String shortfall = '5.50'}) => {
  'id': 'csh-1',
  'handover_number': 'CSH000003',
  'driver_id': 'drv-1',
  'route_id': 'route-1',
  'expected_amount': '905.50',
  'actual_amount': '900.00',
  'shortfall': shortfall,
  'declared_by': 'user-1',
  'declared_at': '2026-09-02T10:35:24.790933Z',
};

void main() {
  group('CashHandoverApi.getForRoute', () {
    test('parses the expected amount with no handover yet', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse({
          'route_id': 'route-1',
          'driver_id': 'drv-1',
          'route_status': 'completed',
          'route_date': '2026-09-01T12:53:33.563594Z',
          'expected_amount': '1811.00',
          'cash_stop_count': 2,
          'handover': null,
        }, 200);
      });

      final result = await CashHandoverApi(client.dio).getForRoute('route-1');

      expect(captured!.path, '/api/v1/cash-handovers/for-route/route-1');
      final view = result.when(onSuccess: (v) => v, onFailure: (_) => null);
      expect(view!.expectedAmount, 1811.00);
      expect(view.cashStopCount, 2);
      expect(view.handover, isNull);
      expect(view.isPending, isTrue);
      expect(view.isDeclared, isFalse);
    });

    test('parses a populated handover once declared', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'route_id': 'route-1',
          'driver_id': 'drv-1',
          'route_status': 'completed',
          'route_date': '2026-09-01T12:53:33.563594Z',
          'expected_amount': '905.50',
          'cash_stop_count': 1,
          'handover': _handoverJson(),
        }, 200),
      );

      final result = await CashHandoverApi(client.dio).getForRoute('route-1');

      final view = result.when(onSuccess: (v) => v, onFailure: (_) => null);
      expect(view!.isDeclared, isTrue);
      expect(view.isPending, isFalse);
      expect(view.handover!.handoverNumber, 'CSH000003');
      expect(view.handover!.shortfall, 5.50);
      expect(view.handover!.surplus, 0);
    });

    test('maps a 404 to a failure', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'error_code': 'RESOURCE_NOT_FOUND',
          'detail': 'No route visible with id route-x.',
        }, 404),
      );

      final result = await CashHandoverApi(client.dio).getForRoute('route-x');

      final failure = result.when(onSuccess: (_) => null, onFailure: (f) => f);
      expect(failure!.errorCode, 'RESOURCE_NOT_FOUND');
    });
  });

  group('CashHandoverApi.declare', () {
    test('posts the fixed-2 amount and parses the handover', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse(_handoverJson(shortfall: '0.00'), 201);
      });

      final result = await CashHandoverApi(
        client.dio,
      ).declare(routeId: 'route-1', driverId: 'drv-1', actualAmount: 900);

      expect(captured!.path, '/api/v1/cash-handovers');
      expect(captured!.method, 'POST');
      expect(captured!.data, {
        'driver_id': 'drv-1',
        'route_id': 'route-1',
        'actual_amount': '900.00',
      });
      final handover = result.when(onSuccess: (h) => h, onFailure: (_) => null);
      expect(handover!.handoverNumber, 'CSH000003');
    });

    test('maps a 409 conflict to a failure', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'error_code': 'CONFLICT',
          'detail': 'Cash has already been handed over for this route.',
        }, 409),
      );

      final result = await CashHandoverApi(
        client.dio,
      ).declare(routeId: 'route-1', driverId: 'drv-1', actualAmount: 900);

      final failure = result.when(onSuccess: (_) => null, onFailure: (f) => f);
      expect(failure!.errorCode, 'CONFLICT');
    });
  });
}
