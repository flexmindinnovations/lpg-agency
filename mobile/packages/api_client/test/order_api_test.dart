import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

Map<String, dynamic> _orderJson({String status = 'booked'}) => {
  'id': 'order-1',
  'tenant_id': 'tenant-1',
  'branch_id': 'branch-1',
  'customer_id': 'customer-1',
  'address_id': 'address-1',
  'delivery_address': {'address_line': '221B Baker Street'},
  'status': status,
  'booking_source': 'app',
  'payment_method_preference': null,
  'requested_date': '2026-09-01T00:00:00Z',
  'metadata': <String, dynamic>{},
  'route_stop_id': null,
  'total_amount': 905.5,
  'lines': [
    {
      'id': 'line-1',
      'cylinder_type_id': 'cyl-14kg',
      'quantity_ordered': 1,
      'quantity_delivered': 0,
      'quantity_pending': 1,
      'quantity_collected_empty': 0,
      'is_backordered': false,
      'unit_price': 905.5,
    },
  ],
};

void main() {
  group('OrderApi', () {
    test(
      'createOrder sends an Idempotency-Key header and parses the order',
      () async {
        RequestOptions? capturedOptions;
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          capturedOptions = options;
          return jsonResponse(_orderJson(), 201);
        });
        final orderApi = OrderApi(client.dio);

        final result = await orderApi.createOrder(
          CreateOrderRequest(
            branchId: 'branch-1',
            customerId: 'customer-1',
            addressId: 'address-1',
            deliveryAddress: const DeliveryAddressPayload(
              addressLine: '221B Baker Street',
            ),
            bookingSource: 'app',
            requestedDate: DateTime.utc(2026, 9, 1),
            lines: const [
              CreateOrderLineRequest(cylinderTypeId: 'cyl-14kg', quantity: 1),
            ],
          ),
        );

        expect(capturedOptions!.path, '/api/v1/orders');
        expect(
          capturedOptions!.headers['Idempotency-Key'],
          isNotNull,
          reason: 'the backend rejects POST /orders without this header',
        );
        final order = result.when(onSuccess: (o) => o, onFailure: (_) => null);
        expect(order, isNotNull);
        expect(order!.status, 'booked');
        expect(order.lines, hasLength(1));
      },
    );

    test('createOrder reuses a caller-supplied idempotency key', () async {
      RequestOptions? capturedOptions;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        capturedOptions = options;
        return jsonResponse(_orderJson(), 201);
      });
      final orderApi = OrderApi(client.dio);

      await orderApi.createOrder(
        CreateOrderRequest(
          branchId: 'branch-1',
          customerId: 'customer-1',
          addressId: 'address-1',
          deliveryAddress: const DeliveryAddressPayload(
            addressLine: '221B Baker Street',
          ),
          bookingSource: 'app',
          requestedDate: DateTime.utc(2026, 9, 1),
          lines: const [
            CreateOrderLineRequest(cylinderTypeId: 'cyl-14kg', quantity: 1),
          ],
        ),
        idempotencyKey: 'retry-key-123',
      );

      expect(capturedOptions!.headers['Idempotency-Key'], 'retry-key-123');
    });

    test('cancelOrder parses pendingApproval from the response', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'order': _orderJson(status: 'booked'),
          'pending_approval': true,
        }, 202),
      );
      final orderApi = OrderApi(client.dio);

      final result = await orderApi.cancelOrder('order-1', 'Changed my mind');

      final response = result.when(onSuccess: (r) => r, onFailure: (_) => null);
      expect(response, isNotNull);
      expect(response!.pendingApproval, isTrue);
      expect(response.order.id, 'order-1');
    });

    test('getMyOrders maps a network failure to NETWORK_UNAVAILABLE', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        throw DioException.connectionError(
          requestOptions: options,
          reason: 'connection refused',
        );
      });
      final orderApi = OrderApi(client.dio);

      final result = await orderApi.getMyOrders();

      final failure = result.when(
        onSuccess: (_) => null,
        onFailure: (failure) => failure,
      );
      expect(failure!.errorCode, 'NETWORK_UNAVAILABLE');
    });
  });
}
