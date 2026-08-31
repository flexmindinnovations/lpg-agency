import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('NotificationApi', () {
    test(
      'getMyNotifications parses an items-only response (no total)',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter(
          (options) => jsonResponse({
            'items': [
              {
                'id': 'notif-1',
                'tenant_id': 'tenant-1',
                'notification_type': 'order_status_changed',
                'title': 'Order delivered',
                'body': 'Your order has been delivered.',
                'is_read': false,
                'created_at': '2026-08-01T00:00:00Z',
              },
            ],
          }, 200),
        );
        final notificationApi = NotificationApi(client.dio);

        final result = await notificationApi.getMyNotifications();

        final page = result.when(onSuccess: (p) => p, onFailure: (_) => null);
        expect(page, isNotNull);
        expect(page!.items.single.isRead, isFalse);
      },
    );

    test('getUnreadCount unwraps the count field', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({'count': 3}, 200),
      );
      final notificationApi = NotificationApi(client.dio);

      final result = await notificationApi.getUnreadCount();

      expect(result.when(onSuccess: (c) => c, onFailure: (_) => null), 3);
    });

    test('markRead PATCHes the read sub-path', () async {
      RequestOptions? capturedOptions;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        capturedOptions = options;
        return emptyResponse(200);
      });
      final notificationApi = NotificationApi(client.dio);

      final result = await notificationApi.markRead('notif-1');

      expect(capturedOptions!.method, 'PATCH');
      expect(capturedOptions!.path, '/api/v1/notifications/notif-1/read');
      expect(
        result.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
    });

    test('markAllRead POSTs to read-all', () async {
      RequestOptions? capturedOptions;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        capturedOptions = options;
        return emptyResponse(204);
      });
      final notificationApi = NotificationApi(client.dio);

      final result = await notificationApi.markAllRead();

      expect(capturedOptions!.path, '/api/v1/notifications/read-all');
      expect(
        result.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
    });

    test('registerDevice POSTs the token and platform', () async {
      RequestOptions? capturedOptions;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        capturedOptions = options;
        return emptyResponse(204);
      });
      final notificationApi = NotificationApi(client.dio);

      final result = await notificationApi.registerDevice(
        token: 'fcm-abc',
        platform: 'android',
      );

      expect(capturedOptions!.method, 'POST');
      expect(capturedOptions!.path, '/api/v1/notifications/devices');
      expect(capturedOptions!.data, {'token': 'fcm-abc', 'platform': 'android'});
      expect(
        result.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
    });

    test('unregisterDevice POSTs the token to the unregister sub-path', () async {
      RequestOptions? capturedOptions;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        capturedOptions = options;
        return emptyResponse(204);
      });
      final notificationApi = NotificationApi(client.dio);

      final result = await notificationApi.unregisterDevice('fcm-abc');

      expect(
        capturedOptions!.path,
        '/api/v1/notifications/devices/unregister',
      );
      expect(capturedOptions!.data, {'token': 'fcm-abc'});
      expect(
        result.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
    });
  });
}
