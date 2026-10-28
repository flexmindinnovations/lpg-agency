import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('WeighmentApi', () {
    test('listActiveScales reads the in-service scales', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/scales');
        expect(options.queryParameters['status'], 'active');
        return jsonResponse({
          'items': [
            {
              'id': 's-1',
              'warehouse_id': 'w-1',
              'asset_tag': 'SC-01',
              'is_expired': false,
            },
          ],
          'total': 1,
        }, 200);
      });

      final result = await WeighmentApi(client.dio).listActiveScales();

      final scales = result.when(onSuccess: (s) => s, onFailure: (_) => null);
      expect(scales!.single.assetTag, 'SC-01');
      expect(scales.single.isExpired, isFalse);
    });

    test('recordLoadOut checks every cylinder it weighed', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/routes/r-1/weighment');
        expect(options.method, 'POST');
        final body = options.data as Map<String, dynamic>;
        expect(body['total_cylinders_in_batch'], 4);
        expect(body['cylinders_checked'], 4);
        expect(body['underweight_cylinder_count'], 1);
        return jsonResponse({
          'cylinder_type_id': 't-1',
          'context': 'load_out_full_check',
          'result': 'fail',
          'cylinders_checked': 4,
          'underweight_cylinder_count': 1,
        }, 201);
      });

      final result = await WeighmentApi(client.dio).recordLoadOut(
        'r-1',
        scaleId: 's-1',
        cylinderTypeId: 't-1',
        cylinders: 4,
        underweight: 1,
      );

      final record = result.when(onSuccess: (r) => r, onFailure: (_) => null);
      expect(record!.passesLoadOut, isFalse);
    });
  });
}
