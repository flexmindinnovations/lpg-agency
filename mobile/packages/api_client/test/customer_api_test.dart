import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('CustomerApi', () {
    test(
      'addCustomerAddress strips the JSON quotes dio leaves on a bare-string response',
      () async {
        // dio special-cases a `String` type parameter to
        // `ResponseType.plain`, skipping JSON decoding entirely — a naive
        // `_dio.post<String>()` here would return `'"address-1"'` (quotes
        // included) instead of `'address-1'`.
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter(
          (options) => jsonResponse('address-1', 201),
        );
        final customerApi = CustomerApi(client.dio);

        final result = await customerApi.addCustomerAddress(
          'customer-1',
          const AddCustomerAddressRequest(line1: '221B Baker Street'),
        );

        expect(
          result.when(onSuccess: (id) => id, onFailure: (_) => null),
          'address-1',
        );
      },
    );

    test(
      'updateAddress PUTs to the address path and succeeds on 200',
      () async {
        RequestOptions? capturedOptions;
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          capturedOptions = options;
          return emptyResponse(200);
        });
        final customerApi = CustomerApi(client.dio);

        final result = await customerApi.updateAddress(
          'customer-1',
          'address-1',
          const UpdateCustomerAddressRequest(line1: '221B Baker Street'),
        );

        expect(capturedOptions!.method, 'PUT');
        expect(
          capturedOptions!.path,
          '/api/v1/customers/customer-1/addresses/address-1',
        );
        expect(
          result.when(onSuccess: (_) => true, onFailure: (_) => false),
          isTrue,
        );
      },
    );

    test('setPrimaryAddress PUTs to the primary sub-path', () async {
      RequestOptions? capturedOptions;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        capturedOptions = options;
        return emptyResponse(200);
      });
      final customerApi = CustomerApi(client.dio);

      final result = await customerApi.setPrimaryAddress(
        'customer-1',
        'address-1',
      );

      expect(capturedOptions!.method, 'PUT');
      expect(
        capturedOptions!.path,
        '/api/v1/customers/customer-1/addresses/address-1/primary',
      );
      expect(
        result.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
    });
  });
}
