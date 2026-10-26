import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('FleetApi', () {
    test('listDrivers parses names and status', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/drivers');
        return jsonResponse({
          'items': [
            {
              'id': 'd-1',
              'branch_id': 'b-1',
              'name': 'Ravi Kumar',
              'status': 'active',
            },
          ],
          'total': 1,
        }, 200);
      });

      final result = await FleetApi(client.dio).listDrivers();

      final drivers = result.when(onSuccess: (d) => d, onFailure: (_) => null);
      expect(drivers!.single.name, 'Ravi Kumar');
      expect(drivers.single.isActive, isTrue);
    });

    test('listWarehouses parses the plain list', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/admin/warehouses');
        return jsonResponse([
          {
            'id': 'w-1',
            'branch_id': 'b-1',
            'name': 'Main godown',
            'address_line': 'Plot 4',
            'is_active': true,
          },
        ], 200);
      });

      final result = await FleetApi(client.dio).listWarehouses();

      final godowns = result.when(onSuccess: (w) => w, onFailure: (_) => null);
      expect(godowns!.single.name, 'Main godown');
    });

    test('getFilledStock sums only filled cylinders per type', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(
          options.path,
          '/api/v1/inventory-locations/warehouse/w-1/balance',
        );
        return jsonResponse({
          'balances': [
            {'cylinder_type_id': 'ct-1', 'status': 'filled', 'quantity': 4},
            {'cylinder_type_id': 'ct-1', 'status': 'filled', 'quantity': 2},
            {'cylinder_type_id': 'ct-1', 'status': 'empty', 'quantity': 9},
            {'cylinder_type_id': 'ct-2', 'status': 'empty', 'quantity': 3},
          ],
        }, 200);
      });

      final result = await FleetApi(
        client.dio,
      ).getFilledStock('warehouse', 'w-1');

      final stock = result.when(onSuccess: (s) => s, onFailure: (_) => null);
      expect(stock, {'ct-1': 6});
    });
  });
}
