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
  int? closeCode;

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

  /// The server accepting the auth frame.
  void ready() => emit({'type': 'ready'});

  /// Frames sent after the initial auth frame.
  List<String> get sentAfterAuth => sent.skip(1).toList();

  /// Simulates the connection dropping (server restart, network loss).
  Future<void> dropConnection({int? code}) {
    closeCode = code;
    return _controller.close();
  }
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
        // Nothing but the auth frame until the server says ready.
        expect(sockets.single.sentAfterAuth, isEmpty);
        sockets.single.ready();
        await Future<void>.delayed(Duration.zero);
        expect(sockets.single.sentAfterAuth, [
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
        sockets.single.ready();
        await Future<void>.delayed(Duration.zero);

        // Same intent as subscribeToOrder — no separate subscription.
        expect(sockets.single.sentAfterAuth, [
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
      'the access token goes in the first frame, never in the URL',
      () async {
        Uri? capturedUri;
        final sockets = <_FakeSocket>[];
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => 'jwt-123',
          connect: (uri) {
            capturedUri = uri;
            final socket = _FakeSocket();
            sockets.add(socket);
            return socket;
          },
        );

        client.subscribeToNotifications();
        await Future<void>.delayed(Duration.zero);

        expect(capturedUri!.toString(), 'wss://api.test/api/v1/ws');
        expect(capturedUri!.queryParameters, isEmpty);
        expect(
          sockets.single.sent.first,
          jsonEncode({'type': 'auth', 'token': 'jwt-123'}),
        );
        await client.disconnect();
      },
    );

    test('updateAccessToken re-authenticates in-band once ready', () async {
      var token = 'jwt-1';
      final sockets = <_FakeSocket>[];
      final client = RealtimeClient(
        wsBaseUrl: 'wss://api.test',
        getAccessToken: () => token,
        connect: (uri) {
          final socket = _FakeSocket();
          sockets.add(socket);
          return socket;
        },
      );

      client.subscribeToNotifications();
      await Future<void>.delayed(Duration.zero);
      sockets.single.ready();
      await Future<void>.delayed(Duration.zero);

      token = 'jwt-2';
      client.updateAccessToken();
      expect(
        sockets.single.sent.last,
        jsonEncode({'type': 'auth', 'token': 'jwt-2'}),
      );
      expect(sockets, hasLength(1));
      await client.disconnect();
    });

    test('does not connect without a token and retries later', () {
      fakeAsync((async) {
        String? token;
        final sockets = <_FakeSocket>[];
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => token,
          connect: (uri) {
            final socket = _FakeSocket();
            sockets.add(socket);
            return socket;
          },
        );

        client.subscribeToNotifications();
        async.flushMicrotasks();
        expect(sockets, isEmpty);

        token = 'jwt-1';
        async.elapse(const Duration(seconds: 1));
        expect(sockets, hasLength(1));

        unawaited(client.disconnect());
        async.flushMicrotasks();
      });
    });

    test(
      'subscribeToNotificationReads forwards read and read_all events',
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
        final sub = client.subscribeToNotificationReads().listen(events.add);
        await Future<void>.delayed(Duration.zero);
        sockets.single.ready();
        sockets.single.emit({
          'type': 'notification.read',
          'notification_id': 'n-1',
        });
        sockets.single.emit({'type': 'notification.read_all'});
        sockets.single.emit({'type': 'notification.new'});
        await Future<void>.delayed(Duration.zero);

        expect(events.map((e) => e['type']), [
          'notification.read',
          'notification.read_all',
        ]);
        await sub.cancel();
        await client.disconnect();
      },
    );

    test(
      'subscribeToStaffUpdates subscribes to orders and notifications',
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
        final sub = client.subscribeToStaffUpdates().listen(events.add);
        await Future<void>.delayed(Duration.zero);
        sockets.single.ready();
        await Future<void>.delayed(Duration.zero);
        expect(
          sockets.single.sentAfterAuth
              .map(jsonDecode)
              .map((m) => m['subscribe']),
          contains(containsAll(['orders', 'notifications'])),
        );

        sockets.single.emit({
          'type': 'order.status_changed',
          'order_id': 'o-1',
          'status': 'out_for_delivery',
        });
        sockets.single.emit({'type': 'notification.new', 'title': 'Hi'});
        sockets.single.emit({'type': 'delivery.route_updated'});
        await Future<void>.delayed(Duration.zero);

        expect(events.map((e) => e['type']), [
          'order.status_changed',
          'notification.new',
        ]);
        await sub.cancel();
        await client.disconnect();
      },
    );

    test('subscribeToDriverRoutes subscribes to the driver channel', () async {
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
      final sub = client.subscribeToDriverRoutes().listen(events.add);
      await Future<void>.delayed(Duration.zero);
      sockets.single.ready();
      await Future<void>.delayed(Duration.zero);
      expect(sockets.single.sentAfterAuth, [
        jsonEncode({
          'subscribe': ['driver'],
        }),
      ]);

      sockets.single.emit({
        'type': 'delivery.route_updated',
        'route_id': 'r-1',
      });
      sockets.single.emit({'type': 'order.status_changed'});
      await Future<void>.delayed(Duration.zero);

      expect(events, hasLength(1));
      expect(events.single['route_id'], 'r-1');
      await sub.cancel();
      await client.disconnect();
    });

    test(
      'subscribeToDriverUpdates covers inbox changes, routes and reconnects',
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

          final types = <Object?>[];
          client.subscribeToDriverUpdates().listen((m) => types.add(m['type']));
          async.flushMicrotasks();
          sockets.single.ready();
          async.flushMicrotasks();
          expect(sockets.single.sentAfterAuth, [
            jsonEncode({
              'subscribe': ['driver', 'notifications'],
            }),
          ]);

          sockets.single.emit({'type': 'notification.new'});
          sockets.single.emit({'type': 'notification.read_all'});
          sockets.single.emit({'type': 'delivery.route_updated'});
          sockets.single.emit({'type': 'order.status_changed'});
          async.flushMicrotasks();

          unawaited(sockets.single.dropConnection());
          async.flushMicrotasks();
          async.elapse(const Duration(seconds: 1));
          sockets.last.ready();
          async.flushMicrotasks();

          expect(types, [
            'notification.new',
            'notification.read_all',
            'delivery.route_updated',
            reconnectedMessageType,
          ]);
          unawaited(client.disconnect());
          async.flushMicrotasks();
        });
      },
    );

    test('a rejected token (1008) calls onTokenRejected and reconnects', () {
      fakeAsync((async) {
        var rejections = 0;
        final sockets = <_FakeSocket>[];
        final client = RealtimeClient(
          wsBaseUrl: 'wss://api.test',
          getAccessToken: () => 'the-token',
          onTokenRejected: () async => rejections++,
          connect: (uri) {
            final socket = _FakeSocket();
            sockets.add(socket);
            return socket;
          },
        );

        client.subscribeToNotifications();
        async.flushMicrotasks();
        unawaited(sockets.single.dropConnection(code: 1008));
        async.flushMicrotasks();
        expect(rejections, 1);

        async.elapse(const Duration(seconds: 1));
        expect(sockets, hasLength(2));

        // An ordinary drop is not a token rejection.
        unawaited(sockets.last.dropConnection());
        async.flushMicrotasks();
        expect(rejections, 1);

        unawaited(client.disconnect());
        async.flushMicrotasks();
      });
    });

    test('pause closes the socket and resume reconnects and resubscribes', () {
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
        sockets.single.ready();
        async.flushMicrotasks();

        unawaited(client.pause());
        async.flushMicrotasks();
        expect(sockets.single.closed, isTrue);
        async.elapse(const Duration(seconds: 60));
        expect(sockets, hasLength(1), reason: 'a paused client stays closed');

        client.resume();
        async.flushMicrotasks();
        expect(sockets, hasLength(2));
        sockets.last.ready();
        async.flushMicrotasks();
        expect(sockets.last.sentAfterAuth, [
          jsonEncode({
            'subscribe': ['notifications'],
          }),
        ]);

        unawaited(client.disconnect());
        async.flushMicrotasks();
      });
    });

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

          var reconnects = 0;
          client.reconnected.listen((_) => reconnects++);

          client.subscribeToOrder('order-1');
          async.flushMicrotasks();
          expect(sockets, hasLength(1));
          sockets.first.ready();
          async.flushMicrotasks();
          expect(reconnects, 0, reason: 'the first connect is not a reconnect');

          unawaited(sockets.first.dropConnection());
          async.flushMicrotasks();
          // Not reconnected immediately — waits out the initial 1s backoff.
          expect(sockets, hasLength(1));

          async.elapse(const Duration(seconds: 1));
          expect(sockets, hasLength(2));
          sockets.last.ready();
          async.flushMicrotasks();
          // The new connection replays the still-active subscription and
          // tells listeners to refetch what they missed.
          expect(sockets.last.sentAfterAuth, [
            jsonEncode({
              'subscribe': ['order:order-1'],
            }),
          ]);
          expect(reconnects, 1);

          // A ready connection reset the backoff, so the next drop retries
          // after 1s again.
          unawaited(sockets.last.dropConnection());
          async.flushMicrotasks();
          async.elapse(const Duration(seconds: 1));
          expect(sockets, hasLength(3));

          // That socket never became ready (the server is struggling), so
          // the backoff doubles to 2s — not reconnected at the 1s mark.
          unawaited(sockets.last.dropConnection());
          async.flushMicrotasks();
          async.elapse(const Duration(seconds: 1));
          expect(sockets, hasLength(3));
          async.elapse(const Duration(seconds: 1));
          expect(sockets, hasLength(4));

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
