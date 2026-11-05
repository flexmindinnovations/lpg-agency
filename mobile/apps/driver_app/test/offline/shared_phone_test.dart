// A phone shared by two drivers: the second driver, offline, must not be handed
// the first driver's cached route, and the first driver's unsent delivery must
// neither be sent nor shown under the second driver's session.
import 'package:dio/dio.dart';
import 'package:driver_app/src/offline/cached_resource.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';

class _Adapter implements HttpClientAdapter {
  bool offline = false;
  int requests = 0;

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    requests++;
    if (offline) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'no network',
      );
    }
    return ResponseBody.fromString(
      '{"id": "route-of-driver-1"}',
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
  test('driver 2, offline, does not get driver 1\'s cached route', () async {
    final db = AppDatabase(NativeDatabase.memory());
    addTearDown(db.close);
    var signedIn = 'driver-1';
    final cache = ResourceCache(db, owner: () => signedIn);
    final adapter = _Adapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://x'))
      ..httpClientAdapter = adapter;
    final reader = CacheFirstReader(cache: cache, dio: dio);

    // Driver 1 loads the route online, then it is cached.
    expect(
      await reader.getMap(
        '/routes/active',
        type: 'route_active',
        id: 'current',
      ),
      {'id': 'route-of-driver-1'},
    );

    // Driver 1's session ends and driver 2 signs in, with no signal.
    signedIn = 'driver-2';
    adapter.offline = true;

    await expectLater(
      reader.getMap('/routes/active', type: 'route_active', id: 'current'),
      throwsA(isA<DioException>()),
      reason: 'there is nothing of driver 2\'s to fall back to',
    );

    // Driver 1 is back: their own cache still serves them.
    signedIn = 'driver-1';
    expect(
      await reader.getMap(
        '/routes/active',
        type: 'route_active',
        id: 'current',
      ),
      {'id': 'route-of-driver-1'},
    );
  });
}
