import 'dart:async';
import 'dart:convert';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:realtime/realtime.dart';

class _FakeSocket implements RealtimeSocket {
  final _controller = StreamController<dynamic>.broadcast();
  final List<String> sent = [];
  bool closed = false;

  @override
  Stream<dynamic> get stream => _controller.stream;

  @override
  void send(String message) => sent.add(message);

  @override
  Future<void> close() async {
    closed = true;
    await _controller.close();
  }

  void emit(Map<String, dynamic> message) =>
      _controller.add(jsonEncode(message));

  /// Simulates the connection dropping (server restart, network loss).
  Future<void> dropConnection() => _controller.close();
}

void main() {
  group('RealtimeClient', () {
    test(
      'subscribeToOrder sends a subscribe intent and filters by order id',
      () async {
        final sockets = <_FakeSocket>[];
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => 'the-token',
          connect: (uri) {
            final socket = _FakeSocket();
            sockets.add(socket);
            return socket;
          },
        );

        final events = <Map<String, dynamic>>[];
        final sub = client.subscribeToOrder('order-1').listen(events.add);
        await Future<void>.delayed(Duration.zero);

        expect(sockets, hasLength(1));
        expect(sockets.single.sent, [
          jsonEncode({
            'subscribe': ['order:order-1'],
          }),
        ]);

        sockets.single.emit({
          'type': 'order.status_changed',
          'order_id': 'order-1',
          'status': 'confirmed',
        });
        // A message for a different order must not reach this subscriber.
        sockets.single.emit({
          'type': 'order.status_changed',
          'order_id': 'order-2',
          'status': 'confirmed',
        });
        // A different message type on the same channel must not leak through.
        sockets.single.emit({'type': 'dashboard.metrics_stale'});
        await Future<void>.delayed(Duration.zero);

        expect(events, hasLength(1));
        expect(events.single['order_id'], 'order-1');

        await sub.cancel();
        await client.disconnect();
      },
    );

    test(
      'subscribeToDriverLocation reuses the order channel and filters by type',
      () async {
        final sockets = <_FakeSocket>[];
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => 'the-token',
          connect: (uri) {
            final socket = _FakeSocket();
            sockets.add(socket);
            return socket;
          },
        );

        final events = <Map<String, dynamic>>[];
        final sub = client
            .subscribeToDriverLocation('order-1')
            .listen(events.add);
        await Future<void>.delayed(Duration.zero);

        // Same intent as subscribeToOrder — no separate subscription.
        expect(sockets.single.sent, [
          jsonEncode({
            'subscribe': ['order:order-1'],
          }),
        ]);

        sockets.single.emit({
          'type': 'driver.location',
          'order_id': 'order-1',
          'latitude': 9.93,
          'longitude': 76.26,
        });
        sockets.single.emit({
          'type': 'driver.location',
          'order_id': 'order-2',
          'latitude': 1.0,
          'longitude': 2.0,
        });
        sockets.single.emit({
          'type': 'order.status_changed',
          'order_id': 'order-1',
        });
        await Future<void>.delayed(Duration.zero);

        expect(events, hasLength(1));
        expect(events.single['latitude'], 9.93);

        await sub.cancel();
        await client.disconnect();
      },
    );

    test(
      'subscribeToNotifications filters to notification.new messages',
      () async {
        final sockets = <_FakeSocket>[];
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => 'the-token',
          connect: (uri) {
            final socket = _FakeSocket();
            sockets.add(socket);
            return socket;
          },
        );

        final events = <Map<String, dynamic>>[];
        final sub = client.subscribeToNotifications().listen(events.add);
        await Future<void>.delayed(Duration.zero);

        sockets.single.emit({
          'type': 'notification.new',
          'notification_id': 'notif-1',
        });
        sockets.single.emit({
          'type': 'order.status_changed',
          'order_id': 'order-1',
        });
        await Future<void>.delayed(Duration.zero);

        expect(events, hasLength(1));
        expect(events.single['notification_id'], 'notif-1');

        await sub.cancel();
        await client.disconnect();
      },
    );

    test(
      'the access token is passed as a query parameter on connect',
      () async {
        Uri? capturedUri;
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => 'jwt-123',
          connect: (uri) {
            capturedUri = uri;
            return _FakeSocket();
          },
        );

        client.subscribeToNotifications();
        await Future<void>.delayed(Duration.zero);

        expect(
          capturedUri!.toString(),
          'wss://api.test/api/v1/ws?token=jwt-123',
        );
        await client.disconnect();
      },
    );

    test(
      'replies to a server ping with a pong, without forwarding it',
      () async {
        final sockets = <_FakeSocket>[];
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => 'the-token',
          connect: (uri) {
            final socket = _FakeSocket();
            sockets.add(socket);
            return socket;
          },
        );

        final events = <Map<String, dynamic>>[];
        client.subscribeToNotifications().listen(events.add);
        await Future<void>.delayed(Duration.zero);

        sockets.single.emit({'type': 'ping'});
        await Future<void>.delayed(Duration.zero);

        expect(events, isEmpty);
        expect(sockets.single.sent.last, jsonEncode({'type': 'pong'}));

        await client.disconnect();
      },
    );

    test(
      'reconnects with exponential backoff and replays active subscriptions',
      () {
        fakeAsync((async) {
          final sockets = <_FakeSocket>[];
          final client = RealtimeClient(
            wsBaseUrl: 'wss://api.test',
            getAccessToken: () => 'the-token',
            connect: (uri) {
              final socket = _FakeSocket();
              sockets.add(socket);
              return socket;
            },
          );

          client.subscribeToOrder('order-1');
          async.flushMicrotasks();
          expect(sockets, hasLength(1));

          unawaited(sockets.first.dropConnection());
          async.flushMicrotasks();
          // Not reconnected immediately — waits out the initial 1s backoff.
          expect(sockets, hasLength(1));

          async.elapse(const Duration(seconds: 1));
          expect(sockets, hasLength(2));
          // The new connection replays the still-active subscription.
          expect(sockets.last.sent, [
            jsonEncode({
              'subscribe': ['order:order-1'],
            }),
          ]);

          unawaited(sockets.last.dropConnection());
          async.flushMicrotasks();
          async.elapse(const Duration(seconds: 1));
          // Backoff doubled to 2s — still not reconnected at the old 1s mark.
          expect(sockets, hasLength(2));
          async.elapse(const Duration(seconds: 1));
          expect(sockets, hasLength(3));

          unawaited(client.disconnect());
          async.flushMicrotasks();
        });
      },
    );

    test('disconnect stops further reconnect attempts', () {
      fakeAsync((async) {
        final sockets = <_FakeSocket>[];
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => 'the-token',
          connect: (uri) {
            final socket = _FakeSocket();
            sockets.add(socket);
            return socket;
          },
        );

        client.subscribeToNotifications();
        async.flushMicrotasks();
        expect(sockets, hasLength(1));

        unawaited(client.disconnect());
        async.flushMicrotasks();
        async.elapse(const Duration(seconds: 30));

        expect(
          sockets,
          hasLength(1),
          reason: 'a closed client must not reconnect',
        );
      });
    });
  });
}
