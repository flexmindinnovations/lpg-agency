import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

Map<String, dynamic> _routeJson({String status = 'in_progress'}) => {
  'id': 'route-1',
  'tenant_id': 'tenant-1',
  'branch_id': 'branch-1',
  'driver_id': 'driver-1',
  'vehicle_id': 'vehicle-1',
  'date': '2026-09-01T00:00:00Z',
  'status': status,
  'version': 1,
  'stops': [
    {
      'id': 'stop-1',
      'route_id': 'route-1',
      'order_id': 'order-1',
      'sequence_number': 0,
      'status': 'pending',
    },
  ],
};

void main() {
  group('RouteApi', () {
    test('getMyActiveRoute parses the route and its stops', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/routes/active');
        return jsonResponse(_routeJson(), 200);
      });

      final result = await RouteApi(client.dio).getMyActiveRoute();

      final route = result.when(onSuccess: (r) => r, onFailure: (_) => null);
      expect(route!.isInProgress, isTrue);
      expect(route.stops.single.orderId, 'order-1');
    });

    test('getMyActiveRoute maps a 404 to Success(null)', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        return jsonResponse({'detail': 'no route'}, 404);
      });

      final result = await RouteApi(client.dio).getMyActiveRoute();

      final route = result.when(
        onSuccess: (r) => r,
        onFailure: (_) => throw StateError('should be Success(null)'),
      );
      expect(route, isNull);
    });

    test('listRoutes parses the page items and forwards status', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse({
          'items': [
            _routeJson(status: 'completed'),
            _routeJson(status: 'reconciled'),
          ],
          'total': 2,
          'page': 1,
          'page_size': 20,
        }, 200);
      });

      final result = await RouteApi(client.dio).listRoutes(status: 'completed');

      expect(captured!.path, '/api/v1/routes');
      expect(captured!.queryParameters['status'], 'completed');
      final routes = result.when(onSuccess: (r) => r, onFailure: (_) => null);
      expect(routes, hasLength(2));
      expect(routes!.first.status, 'completed');
    });

    test('listRoutes omits status when not given', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse({
          'items': <dynamic>[],
          'total': 0,
          'page': 1,
          'page_size': 20,
        }, 200);
      });

      await RouteApi(client.dio).listRoutes();

      expect(captured!.queryParameters.containsKey('status'), isFalse);
    });

    test('reportLocation posts the ping body and succeeds on 204', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return emptyResponse(204);
      });

      final result = await RouteApi(client.dio).reportLocation(
        'route-1',
        const DriverLocationReport(
          latitude: 9.93,
          longitude: 76.26,
          heading: 42,
        ),
      );

      expect(result.when(onSuccess: (_) => true, onFailure: (_) => false),
          isTrue);
      expect(captured!.path, '/api/v1/routes/route-1/location');
      expect(captured!.data, {
        'latitude': 9.93,
        'longitude': 76.26,
        'heading': 42,
      });
    });
  });
}
