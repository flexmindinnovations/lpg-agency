import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/van_load/data/van_load_provider.dart';
import 'package:driver_app/src/features/van_load/presentation/van_load_screen.dart';
import 'package:driver_app/src/offline/pending_sync.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../../support/offline_harness.dart';

RouteSummary _route({
  String status = 'loaded',
  String? confirmedAt,
  List<RouteLoadLine> lines = const [],
}) => RouteSummary(
  id: 'r1',
  status: status,
  driverId: 'd1',
  vehicleId: 'v1',
  stops: const [],
  date: DateTime(2026, 9, 3),
  loadedLines: lines,
  loadConfirmedAt: confirmedAt == null ? null : DateTime.parse(confirmedAt),
);

class _OkAdapter implements HttpClientAdapter {
  final List<String> paths = [];
  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    paths.add(options.path);
    return ResponseBody.fromString(
      '{}',
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Widget _host(OfflineHarness harness, {required RouteSummary route}) {
  return ProviderScope(
    overrides: [
      ...harness.overrides,
      activeRouteProvider.overrideWith((ref) async => route),
      cylinderTypeNamesProvider.overrideWith(
        (ref) async => {'ct-14kg': '14.2 kg', 'ct-19kg': '19 kg'},
      ),
      // The screen watches this live drift stream; a plain stream keeps
      // pumpAndSettle from hanging on the coordinator's queue watch.
      pendingSyncAggregatesProvider.overrideWith(
        (ref) => Stream.value(const <String>{}),
      ),
    ],
    child: MaterialApp.router(
      theme: LpgTheme.light,
      routerConfig: GoRouter(
        initialLocation: '/load',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) => const Scaffold(body: Text('home')),
          ),
          GoRoute(
            path: '/load',
            builder: (_, _) => const VanLoadScreen(routeId: 'r1'),
          ),
        ],
      ),
    ),
  );
}

void main() {
  late OfflineHarness harness;

  setUp(() {
    harness = OfflineHarness(
      ApiClient(baseUrl: 'https://api.test')
        ..dio.httpClientAdapter = _OkAdapter(),
    );
  });
  tearDown(() => harness.dispose());

  testWidgets('renders the manifest with resolved cylinder names', (
    tester,
  ) async {
    await tester.pumpWidget(
      _host(
        harness,
        route: _route(
          lines: const [
            RouteLoadLine(cylinderTypeId: 'ct-14kg', quantity: 5),
            RouteLoadLine(cylinderTypeId: 'ct-19kg', quantity: 2),
          ],
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('14.2 kg'), findsOneWidget);
    expect(find.text('× 5'), findsOneWidget);
    expect(find.textContaining('7 cylinders'), findsOneWidget);
    expect(find.widgetWithText(LpgButton, 'Confirm load'), findsOneWidget);
  });

  testWidgets('Confirm load queues a route_confirm_load op and goes home', (
    tester,
  ) async {
    await tester.pumpWidget(
      _host(
        harness,
        route: _route(
          lines: const [RouteLoadLine(cylinderTypeId: 'ct-14kg', quantity: 5)],
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(LpgButton, 'Confirm load'));
    await tester.pumpAndSettle();

    final ops = await harness.ops();
    expect(ops.single.type, 'route_confirm_load');
    expect(
      jsonDecode(ops.single.payload)['path'],
      '/api/v1/routes/r1/confirm-load',
    );
    expect(find.text('home'), findsOneWidget);
  });

  testWidgets('an already-confirmed load shows the notice, no button', (
    tester,
  ) async {
    await tester.pumpWidget(
      _host(
        harness,
        route: _route(
          confirmedAt: '2026-09-03T10:00:00Z',
          lines: const [RouteLoadLine(cylinderTypeId: 'ct-14kg', quantity: 5)],
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('You confirmed this load'), findsOneWidget);
    expect(find.widgetWithText(LpgButton, 'Confirm load'), findsNothing);
  });
}
