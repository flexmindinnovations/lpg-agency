import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/features/notifications/data/notifications_provider.dart';
import 'package:driver_app/src/features/notifications/presentation/notifications_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

NotificationResponse _n({
  String id = 'n1',
  String type = 'route_ready',
  String title = 'Route Ready',
  String body = 'Your route is ready — 5 stops.',
  String? refType = 'route',
  String? refId,
  bool isRead = false,
}) => NotificationResponse(
  id: id,
  tenantId: 't1',
  notificationType: type,
  title: title,
  body: body,
  referenceType: refType,
  referenceId: refId,
  isRead: isRead,
  createdAt: DateTime(2026, 9, 2),
);

class _RecordingAdapter implements HttpClientAdapter {
  final paths = <String>[];

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    paths.add('${options.method} ${options.path}');
    return ResponseBody.fromString('{}', 200);
  }

  @override
  void close({bool force = false}) {}
}

Widget _host(ProviderContainer c) => UncontrolledProviderScope(
  container: c,
  child: MaterialApp(theme: LpgTheme.light, home: const NotificationsScreen()),
);

void main() {
  group('NotificationsScreen', () {
    testWidgets('shows the empty state when there are no alerts', (
      tester,
    ) async {
      final c = ProviderContainer(
        overrides: [
          driverNotificationsProvider.overrideWith((ref) async => const []),
        ],
      );
      addTearDown(c.dispose);

      await tester.pumpWidget(_host(c));
      await tester.pumpAndSettle();

      expect(find.text('No alerts yet.'), findsOneWidget);
      expect(find.text('Mark all read'), findsNothing);
    });

    testWidgets('lists alerts, flags the unread ones, and marks all read', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final client = ApiClient(baseUrl: 'https://api.test')
        ..dio.httpClientAdapter = adapter;
      final c = ProviderContainer(
        overrides: [
          apiClientProvider.overrideWithValue(client),
          driverNotificationsProvider.overrideWith(
            (ref) async => [
              _n(id: 'a', title: 'Route Ready'),
              _n(
                id: 'b',
                type: 'stop_cancelled',
                title: 'Stop Cancelled',
                body: 'Order #ABC was cancelled.',
                refType: 'order',
                isRead: true,
              ),
            ],
          ),
          unreadNotificationCountProvider.overrideWith((ref) async => 1),
        ],
      );
      addTearDown(c.dispose);

      await tester.pumpWidget(_host(c));
      await tester.pumpAndSettle();

      expect(find.text('Route Ready'), findsOneWidget);
      expect(find.text('Stop Cancelled'), findsOneWidget);

      await tester.tap(find.text('Mark all read'));
      await tester.pumpAndSettle();

      expect(adapter.paths, contains('POST /api/v1/notifications/read-all'));
    });
  });
}
