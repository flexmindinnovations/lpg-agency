// Story 0.4: the dashboard must show its skeleton until the first answer, retry
// a failed first request once without showing an error, show the error only if
// that also fails, and keep the numbers on screen while it refreshes.
import 'dart:convert';
import 'dart:typed_data';

import 'package:admin_app/src/features/approvals/data/approvals_provider.dart';
import 'package:admin_app/src/features/compliance/data/compliance_provider.dart';
import 'package:admin_app/src/features/dashboard/data/dashboard_providers.dart';
import 'package:admin_app/src/features/dashboard/presentation/dashboard_screen.dart';
import 'package:admin_app/src/features/dispatch/data/dispatch_provider.dart';
import 'package:admin_app/src/features/notifications/data/notifications_provider.dart';
import 'package:admin_app/src/features/orders/data/orders_provider.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// What the fake server does with one request.
sealed class _Reply {
  const _Reply();
}

/// The request never reaches the server (radio asleep, no route yet).
class _NoNetwork extends _Reply {
  const _NoNetwork();
}

/// A gateway answers for a server that is still starting.
class _BadGateway extends _Reply {
  const _BadGateway();
}

/// The server answers on purpose: the person may not see this.
class _Forbidden extends _Reply {
  const _Forbidden();
}

/// A normal answer.
class _Ok extends _Reply {
  const _Ok(this.body);
  final Map<String, dynamic> body;
}

/// A scripted server: each path plays its replies in order and repeats the
/// last one.
class _FakeServer implements HttpClientAdapter {
  _FakeServer(this.script);

  final Map<String, List<_Reply>> script;
  final Map<String, int> calls = {};

  int callsTo(String path) => calls[path] ?? 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final path = options.path;
    final index = calls[path] = callsTo(path) + 1;
    final replies = script[path] ?? const [_Ok({})];
    final reply = replies[(index - 1).clamp(0, replies.length - 1)];
    switch (reply) {
      case _NoNetwork():
        throw DioException(
          requestOptions: options,
          type: DioExceptionType.connectionError,
        );
      case _BadGateway():
        return ResponseBody.fromString('<html>502</html>', 502);
      case _Forbidden():
        return ResponseBody.fromString(
          jsonEncode({'error_code': 'FORBIDDEN', 'detail': 'No access.'}),
          403,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        );
      case _Ok(:final body):
        return ResponseBody.fromString(
          jsonEncode(body),
          200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        );
    }
  }

  @override
  void close({bool force = false}) {}
}

const _summaryPath = '/api/v1/dashboard/summary';
const _opsPath = '/api/v1/dashboard/operations';

_Ok _ops(int bookings) => _Ok({
  'orders': {
    'bookings_today': bookings,
    'open_by_status': <String, int>{},
    'delivered_today': 0,
    'failed_today': 0,
    'pending_cancellations': 0,
  },
});

const _summary = _Ok({'customer_count': 7});

Future<_FakeServer> _pumpDashboard(
  WidgetTester tester,
  Map<String, List<_Reply>> script, {
  required Duration? Function(int, Object) retry,
}) async {
  // Tall enough that the whole list is built; a ListView builds lazily.
  tester.view.physicalSize = const Size(800, 4000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final server = _FakeServer(script);
  final dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
    ..httpClientAdapter = server;
  await tester.pumpWidget(
    ProviderScope(
      retry: retry,
      overrides: [
        adminApiProvider.overrideWithValue(AdminApi(dio)),
        // The dashboard also reads these; they are not what is under test.
        fleetProvider.overrideWith(
          (ref) => const FleetData(drivers: [], vehicles: [], warehouses: []),
        ),
        dispatchTripsProvider.overrideWith((ref) => <RouteSummary>[]),
        pendingCashHandoversProvider.overrideWith((ref) => []),
        complianceDueCountProvider.overrideWith((ref) => 0),
        unreadNotificationCountProvider.overrideWith((ref) => 0),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const DashboardScreen()),
    ),
  );
  return server;
}

Duration? _neverRetry(int _, Object _) => null;

final _errorState = find.byType(LpgErrorState);
final _skeleton = find.byType(LpgSkeleton);
final _bookingsToday = find.text("Today's bookings");

Finder _bookings(int n) => find.text('$n');

void main() {
  testWidgets('shows the skeleton, then the numbers, on a healthy start', (
    tester,
  ) async {
    await _pumpDashboard(tester, {
      _opsPath: [_ops(12)],
      _summaryPath: [_summary],
    }, retry: quietRetry);

    expect(_skeleton, findsWidgets);
    expect(_errorState, findsNothing);

    await tester.pump(const Duration(milliseconds: 50));

    expect(_errorState, findsNothing);
    expect(_bookingsToday, findsOneWidget);
    expect(_bookings(12), findsOneWidget);
  });

  group('a first request that fails because the network is not up yet', () {
    final script = {
      _opsPath: [const _NoNetwork(), _ops(12)],
      _summaryPath: [const _NoNetwork(), _summary],
    };

    testWidgets('REPRO: with retries off, the error shows, then the data '
        'arrives on the next refresh', (tester) async {
      await _pumpDashboard(tester, script, retry: _neverRetry);
      await tester.pump(const Duration(milliseconds: 50));

      // This is the owner's "error screen, then the data".
      expect(_errorState, findsWidgets);
      expect(_bookingsToday, findsNothing);

      await tester.tap(find.text('Retry').first);
      await tester.pump(const Duration(milliseconds: 50));
      expect(_bookingsToday, findsOneWidget);
    });

    testWidgets('retries once, quietly: skeleton the whole time, never the '
        'error, then the data', (tester) async {
      final server = await _pumpDashboard(tester, script, retry: quietRetry);

      // First attempt has failed; the retry is waiting out its delay.
      await tester.pump(const Duration(milliseconds: 50));
      expect(_errorState, findsNothing);
      expect(_skeleton, findsWidgets);
      expect(_bookingsToday, findsNothing);

      // Just before the retry fires: still quiet.
      await tester.pump(quietRetryDelay - const Duration(milliseconds: 100));
      expect(_errorState, findsNothing);
      expect(_skeleton, findsWidgets);

      // The retry runs and the numbers appear.
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 50));
      expect(_errorState, findsNothing);
      expect(_bookingsToday, findsOneWidget);
      expect(_bookings(12), findsOneWidget);
      expect(server.callsTo(_opsPath), 2);
    });
  });

  testWidgets('a gateway error while the server starts gets the same quiet '
      'retry', (tester) async {
    await _pumpDashboard(tester, {
      _opsPath: [const _BadGateway(), _ops(3)],
      _summaryPath: [const _BadGateway(), _summary],
    }, retry: quietRetry);

    await tester.pump(const Duration(milliseconds: 50));
    expect(_errorState, findsNothing);

    await tester.pump(quietRetryDelay + const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 50));
    expect(_errorState, findsNothing);
    expect(_bookings(3), findsOneWidget);
  });

  testWidgets('shows the error only when the retry fails too, and Retry '
      'recovers', (tester) async {
    final server = await _pumpDashboard(tester, {
      _opsPath: [const _NoNetwork(), const _NoNetwork(), _ops(5)],
      _summaryPath: [_summary],
    }, retry: quietRetry);

    await tester.pump(const Duration(milliseconds: 50));
    expect(_errorState, findsNothing);

    await tester.pump(quietRetryDelay + const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 50));
    expect(_errorState, findsOneWidget);
    expect(server.callsTo(_opsPath), 2);

    await tester.tap(find.text('Retry'));
    await tester.pump(const Duration(milliseconds: 50));
    expect(_errorState, findsNothing);
    expect(_bookings(5), findsOneWidget);
  });

  testWidgets('does not retry an answer that will not change', (tester) async {
    final server = await _pumpDashboard(tester, {
      _opsPath: [_ops(1)],
      _summaryPath: [const _Forbidden()],
    }, retry: quietRetry);

    // Shown at once: asking again would only return the same refusal.
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));
    expect(_errorState, findsOneWidget);

    await tester.pump(quietRetryDelay * 2);
    expect(server.callsTo(_summaryPath), 1);
  });

  testWidgets('keeps the old numbers on screen while it refreshes, and when '
      'the refresh fails', (tester) async {
    final server = await _pumpDashboard(tester, {
      _opsPath: [_ops(12), const _NoNetwork(), const _NoNetwork(), _ops(13)],
      _summaryPath: [_summary],
    }, retry: quietRetry);
    await tester.pump(const Duration(milliseconds: 50));
    expect(_bookings(12), findsOneWidget);

    final container = ProviderScope.containerOf(
      tester.element(find.byType(DashboardScreen)),
    );

    // A refresh begins and fails: the old data stays, no skeleton, no error.
    container.invalidate(operationsSnapshotProvider);
    await tester.pump(const Duration(milliseconds: 50));
    expect(_bookings(12), findsOneWidget);
    expect(_errorState, findsNothing);

    // The retry also fails: the old data is still better than an error screen.
    await tester.pump(quietRetryDelay + const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 50));
    expect(_bookings(12), findsOneWidget);
    expect(_errorState, findsNothing);
    expect(server.callsTo(_opsPath), 3);

    // The next refresh succeeds and replaces the numbers.
    container.invalidate(operationsSnapshotProvider);
    await tester.pump(const Duration(milliseconds: 50));
    expect(_bookings(13), findsOneWidget);
  });
}
