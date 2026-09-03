import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('DriverApi', () {
    test('getMe parses the profile and its vehicle', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse({
          'driver_id': 'drv-1',
          'name': 'Ramesh Kumar',
          'phone_number': '+919000011111',
          'license_number': 'DL-9001',
          'license_expiry_date': '2030-06-30',
          'status': 'active',
          'vehicle': {
            'registration_number': 'TS07UB4412',
            'make': 'Tata',
            'model': 'Ace',
          },
        }, 200);
      });

      final result = await DriverApi(client.dio).getMe();

      expect(captured!.path, '/api/v1/drivers/me');
      final me = result.when(onSuccess: (m) => m, onFailure: (_) => null);
      expect(me!.name, 'Ramesh Kumar');
      expect(me.licenseExpiryDate, DateTime(2030, 6, 30));
      expect(me.vehicle!.registrationNumber, 'TS07UB4412');
      expect(me.vehicle!.label, 'Tata Ace');
    });

    test('getMe allows a null vehicle', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'driver_id': 'drv-1',
          'name': 'Ramesh Kumar',
          'phone_number': '+919000011111',
          'license_number': 'DL-9001',
          'license_expiry_date': null,
          'status': 'active',
          'vehicle': null,
        }, 200),
      );

      final result = await DriverApi(client.dio).getMe();

      final me = result.when(onSuccess: (m) => m, onFailure: (_) => null);
      expect(me!.vehicle, isNull);
      expect(me.licenseExpiryDate, isNull);
    });

    test('getMe maps a 404 to a failure', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'error_code': 'RESOURCE_NOT_FOUND',
          'detail': 'No driver profile for this account.',
        }, 404),
      );

      final result = await DriverApi(client.dio).getMe();

      final failure = result.when(onSuccess: (_) => null, onFailure: (f) => f);
      expect(failure, isNotNull);
    });
  });
}
