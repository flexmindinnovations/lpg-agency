import 'dart:async';
import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:drift/drift.dart' show Value;
import 'package:driver_app/src/features/sync/presentation/sync_status_screen.dart';
import 'package:driver_app/src/offline/sync_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';

import '../../support/offline_harness.dart';

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

SyncOperation _op({
  String id = 'op1',
  String type = 'order_depart',
  String status = 'conflict',
  String? error,
}) => SyncOperation(
  id: id,
  type: type,
  payload: jsonEncode({
    'path': '/api/v1/orders/$id/depart',
    'body': null,
    'aggregateId': 'order-$id-abcdef',
  }),
  status: status,
  createdAt: DateTime(2026, 9, 3),
  errorMessage: error,
  idempotencyKey: id,
  retryCount: 0,
  lastAttemptAt: null,
);

void main() {
  late OfflineHarness harness;
  late StreamController<List<SyncOperation>> issues;
  late StreamController<int> pending;

  setUp(() {
    harness = OfflineHarness(
      ApiClient(baseUrl: 'https://api.test')
        ..dio.httpClientAdapter = _OkAdapter(),
    );
    issues = StreamController<List<SyncOperation>>.broadcast();
    pending = StreamController<int>.broadcast();
  });

  tearDown(() async {
    await issues.close();
    await pending.close();
    await harness.dispose();
  });

  Widget host() => ProviderScope(
    overrides: [
      ...harness.overrides,
      syncIssuesProvider.overrideWith((ref) => issues.stream),
      pendingSyncCountProvider.overrideWith((ref) => pending.stream),
    ],
    child: MaterialApp(theme: LpgTheme.light, home: const SyncStatusScreen()),
  );

  testWidgets('empty queue shows the all-clear state', (tester) async {
    await tester.pumpWidget(host());
    pending.add(0);
    issues.add(const []);
    await tester.pumpAndSettle();

    expect(find.text("Everything's synced."), findsOneWidget);
  });

  testWidgets('a conflict renders REJECTED and discards on acknowledge', (
    tester,
  ) async {
    // Seed a real row so `discardOperation` has something to delete.
    await harness.db
        .into(harness.db.syncOperations)
        .insert(
          SyncOperationsCompanion.insert(
            id: 'op1',
            type: 'order_depart',
            payload: '{"aggregateId":"order-op1"}',
            idempotencyKey: 'op1',
          ),
        );

    await tester.pumpWidget(host());
    pending.add(0);
    issues.add([_op(status: 'conflict')]);
    await tester.pumpAndSettle();

    expect(find.text('REJECTED'), findsOneWidget);
    expect(find.textContaining('Start delivery'), findsOneWidget);

    await tester.tap(find.text('Acknowledge & discard'));
    await tester.pumpAndSettle();

    expect(await harness.ops(), isEmpty);
  });

  testWidgets('a failed op offers Retry, which re-queues the op', (
    tester,
  ) async {
    await harness.db
        .into(harness.db.syncOperations)
        .insert(
          SyncOperationsCompanion.insert(
            id: 'op1',
            type: 'order_depart',
            payload: jsonEncode({
              'path': '/api/v1/orders/op1/depart',
              'body': null,
              'aggregateId': 'order-op1',
            }),
            idempotencyKey: 'op1',
            status: const Value('failed'),
            retryCount: const Value(8),
          ),
        );

    await tester.pumpWidget(host());
    pending.add(0);
    issues.add([_op(status: 'failed', error: 'Cannot reach the server.')]);
    await tester.pumpAndSettle();

    expect(find.text('FAILED'), findsOneWidget);
    expect(find.text('Cannot reach the server.'), findsOneWidget);

    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    // Retry resets the row to pending (retryCount 0) so the queue picks it up.
    final op = (await harness.ops()).single;
    expect(op.retryCount, 0);
    expect(op.status, anyOf('pending', 'syncing', 'synced'));
  });
}
