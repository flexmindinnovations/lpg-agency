import 'package:dio/dio.dart';
import 'package:driver_app/src/offline/cached_resource.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';

class _FakeAdapter implements HttpClientAdapter {
  int status = 200;
  String body = '{"status": "fresh"}';
  bool fail = false;

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    if (fail) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'no network',
      );
    }
    return ResponseBody.fromString(
      body,
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  late AppDatabase db;
  late ResourceCache cache;
  late Dio dio;
  late _FakeAdapter adapter;

  setUp(() {
    db = AppDatabase(NativeDatabase.memory());
    cache = ResourceCache(db);
    adapter = _FakeAdapter();
    dio = Dio(BaseOptions(baseUrl: 'http://localhost'))
      ..httpClientAdapter = adapter;
  });

  tearDown(() => db.close());

  test(
    'a successful GET returns the body and writes it through to the cache',
    () async {
      final resource = CacheFirstReader(cache: cache, dio: dio);

      final first = await resource.getMap('/x', type: 'order', id: 'o1');
      expect(first, {'status': 'fresh'});
      expect(await cache.read('order', 'o1'), {'status': 'fresh'});
    },
  );

  test('a network failure falls back to the cached body', () async {
    await cache.write('order', 'o1', {'status': 'stale'});
    adapter.fail = true;
    final resource = CacheFirstReader(cache: cache, dio: dio);

    final result = await resource.getMap('/x', type: 'order', id: 'o1');
    expect(result, {'status': 'stale'});
  });

  test('a network failure with nothing cached rethrows', () async {
    adapter.fail = true;
    final resource = CacheFirstReader(cache: cache, dio: dio);

    expect(
      () => resource.getMap('/x', type: 'order', id: 'o1'),
      throwsA(isA<DioException>()),
    );
  });

  test('absentWhen returns null and evicts the cached copy', () async {
    await cache.write('route_active', 'current', {'id': 'r1'});
    adapter
      ..fail = false
      ..status = 404
      ..body = '{"error": "not found"}';
    final resource = CacheFirstReader(cache: cache, dio: dio);

    final result = await resource.getMap(
      '/routes/active',
      type: 'route_active',
      id: 'current',
      absentWhen: (e) => e.response?.statusCode == 404,
    );
    expect(result, isNull);
    expect(await cache.read('route_active', 'current'), isNull);
  });

  test('a null cache degrades to a plain pass-through', () async {
    adapter.fail = true;
    final resource = CacheFirstReader(cache: null, dio: dio);

    expect(
      () => resource.getMap('/x', type: 'order', id: 'o1'),
      throwsA(isA<DioException>()),
    );
  });
}
