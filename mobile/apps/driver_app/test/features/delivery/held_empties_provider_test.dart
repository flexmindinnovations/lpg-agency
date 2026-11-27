import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/features/delivery/data/held_empties_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/offline_harness.dart';

class _EmptiesAdapter implements HttpClientAdapter {
  bool offline = false;
  final paths = <String>[];

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    if (offline) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'offline',
      );
    }
    paths.add(options.path);
    return ResponseBody.fromString(
      jsonEncode([
        {
          'cylinder_type_id': 'ct1',
          'cylinder_type_name': '14.2 kg',
          'quantity_held': 10,
        },
      ]),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  late _EmptiesAdapter adapter;
  late OfflineHarness harness;

  setUp(() {
    adapter = _EmptiesAdapter();
    harness = OfflineHarness(
      ApiClient(baseUrl: 'https://api.test')..dio.httpClientAdapter = adapter,
    );
  });

  tearDown(() => harness.dispose());

  Future<List<HeldEmpties>?> read() async {
    final container = ProviderContainer(overrides: harness.overrides);
    addTearDown(container.dispose);
    final subscription = container.listen(heldEmptiesProvider('o1'), (_, _) {});
    addTearDown(subscription.close);
    return container.read(heldEmptiesProvider('o1').future);
  }

  test('reads what the customer holds for the order', () async {
    final held = await read();

    expect(adapter.paths, ['/api/v1/orders/o1/empties']);
    expect(held!.single.cylinderTypeName, '14.2 kg');
    expect(held.single.quantityHeld, 10);
  });

  test('serves the last figures when offline', () async {
    await read();
    adapter.offline = true;

    expect((await read())!.single.quantityHeld, 10);
  });

  test('is unknown when never loaded', () async {
    adapter.offline = true;

    expect(await read(), isNull);
  });
}
