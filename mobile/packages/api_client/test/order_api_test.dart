import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
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

    test(
      'getOrderTracking parses the destination and driver location',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          expect(options.path, '/api/v1/orders/order-1/tracking');
          return jsonResponse({
            'order_id': 'order-1',
            'status': 'out_for_delivery',
            'destination_latitude': 9.9312,
            'destination_longitude': 76.2673,
            'destination_label': '221B Baker Street',
            'route_status': 'in_progress',
            'driver_location': {
              'latitude': 9.94,
              'longitude': 76.27,
              'heading': 90.0,
              'recorded_at': '2026-09-01T10:00:00Z',
            },
            'driver': {
              'name': 'Ramesh Kumar',
              'phone_number': '+919000011111',
              'vehicle_number': 'TS07UB4412',
              'vehicle_model': 'Tata Ace',
            },
          }, 200);
        });

        final result = await OrderApi(client.dio).getOrderTracking('order-1');

        final tracking = result.when(
          onSuccess: (data) => data,
          onFailure: (_) => null,
        );
        expect(tracking!.routeStatus, 'in_progress');
        expect(tracking.destinationLatitude, 9.9312);
        expect(tracking.driverLocation!.heading, 90.0);
        expect(tracking.driver!.name, 'Ramesh Kumar');
        expect(tracking.driver!.vehicleNumber, 'TS07UB4412');
      },
    );

    test('departOrder posts to the depart action', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse(_orderJson(status: 'out_for_delivery'), 200);
      });

      final result = await OrderApi(client.dio).departOrder('order-1');

      expect(captured!.method, 'POST');
      expect(captured!.path, '/api/v1/orders/order-1/depart');
      expect(
        result.when(onSuccess: (o) => o.status, onFailure: (_) => null),
        'out_for_delivery',
      );
    });

    test('resendDeliveryOtp posts to the delivery-otp action', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return emptyResponse(204);
      });

      final result = await OrderApi(client.dio).resendDeliveryOtp('order-1');

      expect(captured!.method, 'POST');
      expect(captured!.path, '/api/v1/orders/order-1/delivery-otp');
      expect(
        result.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
    });

    test('fetchDevDeliveryOtp reads the code from the dev inbox', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse({'code': '482913'}, 200);
      });

      final result = await OrderApi(client.dio).fetchDevDeliveryOtp('order-1');

      expect(captured!.path, '/api/v1/dev/orders/order-1/delivery-otp');
      expect(
        result.when(onSuccess: (code) => code, onFailure: (_) => null),
        '482913',
      );
    });

    test('recordFailedDelivery sends the reason and optional action', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse(_orderJson(status: 'failed_delivery'), 200);
      });

      await OrderApi(client.dio).recordFailedDelivery(
        'order-1',
        reasonCode: 'customer_unavailable',
        resolutionAction: 'reschedule',
      );

      expect(captured!.path, '/api/v1/orders/order-1/failed-delivery');
      expect(captured!.data, {
        'reason_code': 'customer_unavailable',
        'resolution_action': 'reschedule',
      });
    });

    test('recordFailedDelivery omits a null action', () async {
      RequestOptions? captured;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        captured = options;
        return jsonResponse(_orderJson(status: 'failed_delivery'), 200);
      });

      await OrderApi(
        client.dio,
      ).recordFailedDelivery('order-1', reasonCode: 'wrong_address');

      expect(captured!.data, {'reason_code': 'wrong_address'});
    });

    test(
      'uploadPodAttachment posts multipart and parses the blob ref',
      () async {
        RequestOptions? captured;
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          captured = options;
          return jsonResponse({
            'blob_ref': 'tenant/x/orders/o1/pod/abc.png',
          }, 201);
        });

        final result = await OrderApi(client.dio).uploadPodAttachment(
          'o1',
          bytes: const [1, 2, 3],
          filename: 'signature.png',
        );

        expect(captured!.path, '/api/v1/orders/o1/pod-attachments');
        expect(captured!.data, isA<FormData>());
        expect(
          result.when(onSuccess: (r) => r.blobRef, onFailure: (_) => null),
          'tenant/x/orders/o1/pod/abc.png',
        );
      },
    );

    test(
      'deliverOrder sends lines, otp and PoD with an Idempotency-Key',
      () async {
        RequestOptions? captured;
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          captured = options;
          return jsonResponse({'order': _orderJson(status: 'delivered')}, 200);
        });

        final result = await OrderApi(client.dio).deliverOrder(
          'o1',
          const DeliverOrderRequest(
            lines: [
              DeliveredLineRequest(
                cylinderTypeId: 'ct1',
                quantityDelivered: 2,
                quantityCollectedEmpty: 2,
              ),
            ],
            otpCode: '123456',
            proofOfDelivery: ProofOfDeliverySubmission(
              signatureBlobRef: 'sig',
              photoBlobRef: 'photo',
              gpsLat: 17.44,
              gpsLng: 78.35,
              paymentMethod: 'cash',
              amountCollected: 905.5,
            ),
          ),
          idempotencyKey: 'key-1',
        );

        expect(captured!.path, '/api/v1/orders/o1/deliver');
        expect(captured!.headers['Idempotency-Key'], 'key-1');
        final body = captured!.data as Map;
        expect(body['otp_code'], '123456');
        expect((body['proof_of_delivery'] as Map)['payment_method'], 'cash');
        expect(
          result.when(onSuccess: (r) => r.order.status, onFailure: (_) => null),
          'delivered',
        );
      },
    );

    test('getOrderTracking allows a null driver location', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        return jsonResponse({
          'order_id': 'order-1',
          'status': 'confirmed',
          'destination_latitude': null,
          'destination_longitude': null,
          'destination_label': '221B Baker Street',
          'route_status': null,
          'driver_location': null,
        }, 200);
      });

      final result = await OrderApi(client.dio).getOrderTracking('order-1');

      final tracking = result.when(
        onSuccess: (data) => data,
        onFailure: (_) => null,
      );
      expect(tracking!.driverLocation, isNull);
      expect(tracking.destinationLatitude, isNull);
    });

    test(
      'getDeliveryCode reads the code, or null when none is pending',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        var pending = true;
        String? path;
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          path = options.path;
          return pending
              ? jsonResponse({'code': '554210'}, 200)
              : ResponseBody.fromString(
                  'null',
                  200,
                  headers: {
                    Headers.contentTypeHeader: [Headers.jsonContentType],
                  },
                );
        });
        final api = OrderApi(client.dio);

        final code = await api.getDeliveryCode('order-1');
        expect(path, '/api/v1/orders/order-1/delivery-code');
        expect(code.when(onSuccess: (c) => c, onFailure: (_) => 'x'), '554210');

        pending = false;
        final none = await api.getDeliveryCode('order-1');
        expect(none.when(onSuccess: (c) => c, onFailure: (_) => 'x'), isNull);
      },
    );

    test('getPendingCancellation parses the waiting request', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (_) => jsonResponse({
          'id': 'c1',
          'order_id': 'order-1',
          'reason': 'Booked twice',
          'requested_by': 'u1',
          'requested_at': '2026-10-20T10:00:00Z',
        }, 200),
      );

      final result = await OrderApi(
        client.dio,
      ).getPendingCancellation('order-1');
      final request = result.when(onSuccess: (r) => r, onFailure: (_) => null);
      expect(request!.reason, 'Booked twice');
    });

    test('recordFailedDelivery sends the driver note', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      Object? body;
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        body = options.data;
        return jsonResponse(_orderJson(status: 'failed_delivery'), 200);
      });

      await OrderApi(client.dio).recordFailedDelivery(
        'order-1',
        reasonCode: 'customer_unavailable',
        note: 'Back after 6',
      );
      expect(body, {
        'reason_code': 'customer_unavailable',
        'note': 'Back after 6',
      });
    });

    test('confirmOrder posts to the confirm route', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.method, 'POST');
        expect(options.path, '/api/v1/orders/order-1/confirm');
        return jsonResponse(_orderJson(status: 'confirmed'), 200);
      });

      final result = await OrderApi(client.dio).confirmOrder('order-1');

      final order = result.when(onSuccess: (o) => o, onFailure: (_) => null);
      expect(order!.status, 'confirmed');
    });

    test('rejectCancellation sends the reason', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/orders/order-1/cancel/reject');
        expect(options.data, {'reason': 'Already loaded'});
        return jsonResponse({'id': 'c-1'}, 200);
      });

      final result = await OrderApi(
        client.dio,
      ).rejectCancellation('order-1', 'Already loaded');

      expect(result, isA<Success<void>>());
    });

    test('rescheduleOrder sends the new date in UTC', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/orders/order-1/reschedule');
        expect(options.data, {'requested_date': '2026-11-02T00:00:00.000Z'});
        return jsonResponse(_orderJson(status: 'confirmed'), 200);
      });

      final result = await OrderApi(
        client.dio,
      ).rescheduleOrder('order-1', DateTime.utc(2026, 11, 2));

      expect(result, isA<Success<OrderResponse>>());
    });
  });
  group('OrderApi proof of delivery', () {
    test('reads the collected amount, the place and the photo links', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.path, '/api/v1/orders/o-1/proof-of-delivery');
        return jsonResponse({
          'id': 'p-1',
          'tenant_id': 't',
          'order_id': 'o-1',
          'otp_verified_at': '2026-10-30T09:00:00Z',
          'gps_lat': '18.5204',
          'gps_lng': '73.8567',
          'payment_method': 'cash',
          'amount_collected': '905.50',
          'recorded_by': 'u-1',
          'recorded_at': '2026-10-30T09:01:00Z',
          'dac_code': '123456',
          'signature_url': 'https://files.test/sig.png',
          'photo_url': null,
        }, 200);
      });

      final result = await OrderApi(client.dio).getProofOfDelivery('o-1');

      final pod = result.when(onSuccess: (p) => p, onFailure: (_) => null)!;
      expect(pod.amountCollected, 905.5);
      expect(pod.paymentMethod, 'cash');
      expect(pod.gpsLat, 18.5204);
      expect(pod.dacCode, '123456');
      expect(pod.signatureUrl, 'https://files.test/sig.png');
      expect(pod.photoUrl, isNull);
    });

    test('an order not yet delivered has no record', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => ResponseBody.fromString(
          'null',
          200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        ),
      );

      final result = await OrderApi(client.dio).getProofOfDelivery('o-1');

      expect(
        result.when(onSuccess: (p) => p == null, onFailure: (_) => false),
        isTrue,
      );
    });
  });
  group('OrderResponse GST', () {
    Map<String, dynamic> order({
      Object? tax = '45.28',
      Object? payable = '950.78',
    }) => {
      'id': 'o-1',
      'tenant_id': 't',
      'branch_id': 'b',
      'customer_id': 'c',
      'address_id': 'a',
      'delivery_address': {'address_line': '12 MG Road'},
      'status': 'confirmed',
      'booking_source': 'staff',
      'requested_date': '2026-10-30T00:00:00Z',
      'metadata': <String, dynamic>{},
      'total_amount': '905.50',
      'tax_amount': ?tax,
      'payable_amount': ?payable,
      'lines': [
        {
          'id': 'l-1',
          'cylinder_type_id': 'c-1',
          'quantity_ordered': 1,
          'quantity_delivered': 0,
          'quantity_pending': 0,
          'quantity_collected_empty': 0,
          'is_backordered': false,
          'unit_price': '905.50',
          'gst_rate_percent': '5.00',
        },
      ],
    };

    test('reads the price, the GST on it and what the customer pays', () {
      final o = OrderResponse.fromJson(order());

      expect(o.totalAmount, 905.5);
      expect(o.taxAmount, 45.28);
      expect(o.payableAmount, 950.78);
      expect(o.amountToPay, 950.78);
      expect(o.lines.single.gstRatePercent, 5);
    });

    test('an answer without the new fields still has an amount to pay', () {
      final o = OrderResponse.fromJson(order(tax: null, payable: null));

      expect(o.taxAmount, isNull);
      expect(o.payableAmount, isNull);
      expect(o.amountToPay, 905.5);
    });
  });
}
