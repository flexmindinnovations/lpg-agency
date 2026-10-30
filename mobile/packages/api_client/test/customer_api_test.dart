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
  group('CustomerApi staff registration', () {
    Map<String, Object?> customer({String status = 'onboarding'}) => {
      'id': 'cu-1',
      'tenant_id': 't',
      'branch_id': 'b-1',
      'consumer_number': null,
      'full_name': 'Meena Iyer',
      'phone_number': '+919876543210',
      'contact_person': null,
      'alternate_mobile': null,
      'email': null,
      'date_of_birth': null,
      'customer_type': 'domestic',
      'kyc_status': 'pending',
      'status': status,
      'lpg_subsidy_id': null,
      'gstin': null,
      'addresses': <Object>[],
    };

    test(
      'registerCustomer sends the profile and the first address flat',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          expect(options.method, 'POST');
          expect(options.path, '/api/v1/customers');
          expect(options.data, {
            'branch_id': 'b-1',
            'full_name': 'Meena Iyer',
            'phone_number': '+919876543210',
            'customer_type': 'domestic',
            'line_1': 'Flat 4, Shanti Apartments',
            'city': 'Pune',
            'pincode': '411038',
            'address_type': 'delivery',
          });
          return jsonResponse(customer(), 200);
        });

        final result = await CustomerApi(client.dio).registerCustomer(
          const RegisterCustomerRequest(
            branchId: 'b-1',
            fullName: 'Meena Iyer',
            phoneNumber: '+919876543210',
            address: AddCustomerAddressRequest(
              line1: 'Flat 4, Shanti Apartments',
              city: 'Pune',
              pincode: '411038',
            ),
          ),
        );

        final created = result.when(
          onSuccess: (c) => c,
          onFailure: (_) => null,
        )!;
        expect(created.fullName, 'Meena Iyer');
        expect(created.status, 'onboarding');
      },
    );

    test('approveCustomer lets the server pick the consumer number', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/customers/cu-1/approve');
        expect(options.data, {'consumer_number': null});
        return jsonResponse(<String, Object>{}, 200);
      });

      final result = await CustomerApi(client.dio).approveCustomer('cu-1');

      expect(
        result.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
    });
  });
}
