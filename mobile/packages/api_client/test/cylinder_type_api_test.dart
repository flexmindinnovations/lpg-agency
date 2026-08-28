import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('CylinderTypeApi', () {
    test('list parses a bare JSON array response', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse([
          {
            'id': 'cyl-1',
            'name': '14.2kg Domestic',
            'weight_kg': 14.2,
            'is_active': true,
          },
          {
            'id': 'cyl-2',
            'name': 'Commercial 19kg',
            'weight_kg': 19.0,
            'is_active': false,
          },
        ], 200),
      );
      final api = CylinderTypeApi(client.dio);

      final result = await api.list();

      final types = result.when(onSuccess: (t) => t, onFailure: (_) => null);
      expect(types, isNotNull);
      expect(types!.map((t) => t.name), ['14.2kg Domestic', 'Commercial 19kg']);
      expect(types.last.isActive, isFalse);
    });

    test('list parses weight_kg when the backend sends it as a string '
        '(Pydantic Decimal JSON encoding, confirmed live against the real '
        'backend — a bare `num` cast crashed this call)', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse([
          {
            'id': 'cyl-1',
            'name': '14.2kg Domestic',
            'weight_kg': '14.20',
            'is_active': true,
          },
        ], 200),
      );
      final api = CylinderTypeApi(client.dio);

      final result = await api.list();

      final types = result.when(onSuccess: (t) => t, onFailure: (_) => null);
      expect(types, isNotNull);
      expect(types!.single.weightKg, 14.2);
    });
  });
}
