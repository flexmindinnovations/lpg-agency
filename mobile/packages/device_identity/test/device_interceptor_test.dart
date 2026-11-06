import 'package:device_identity/device_identity.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

void main() {
  late DeviceIdentity identity;
  late List<String> refusals;

  setUp(() async {
    identity = await loadIdentity(
      storage: MemoryStorage(installId: 'install-id-0123456789', name: 'Van 2'),
    );
    refusals = [];
  });

  Dio dioWith(ResponseBody Function(RequestOptions) handler) {
    final dio = fakeDio(handler);
    dio.interceptors.insert(
      0,
      DeviceInterceptor(identity: identity, onRefused: refusals.add),
    );
    return dio;
  }

  FakeAdapter adapterOf(Dio dio) => dio.httpClientAdapter as FakeAdapter;

  test('puts the install ID and app type on every request', () async {
    final dio = dioWith((_) => jsonBody({'ok': true}, 200));

    await dio.get<dynamic>('/api/v1/orders');

    final headers = adapterOf(dio).seen.single.headers;
    expect(headers['X-Device-Id'], 'install-id-0123456789');
    expect(headers['X-App-Type'], 'driver_app');
  });

  test(
    'adds the device details to the sign-in, OTP and refresh bodies',
    () async {
      final dio = dioWith((_) => jsonBody({'ok': true}, 200));

      await dio.post<dynamic>(
        '/api/v1/auth/login',
        data: {'email': 'a@b.c', 'password': 'x'},
      );
      await dio.post<dynamic>(
        '/api/v1/auth/otp/verify',
        data: {'tenant_id': 't', 'phone_number': 'p', 'code': '1'},
      );
      await dio.post<dynamic>(
        '/api/v1/auth/refresh',
        data: {'refresh_token': 'r'},
      );

      for (final request in adapterOf(dio).seen) {
        final body = request.data as Map<String, dynamic>;
        expect(body['device'], identity.authBody, reason: request.path);
      }
      final login = adapterOf(dio).seen.first.data as Map<String, dynamic>;
      expect(login['email'], 'a@b.c'); // the original body is kept
    },
  );

  test('leaves every other body alone', () async {
    final dio = dioWith((_) => jsonBody({'ok': true}, 200));

    await dio.post<dynamic>('/api/v1/orders', data: {'qty': 1});
    await dio.post<dynamic>(
      '/api/v1/auth/logout',
      data: {'refresh_token': 'r'},
    );
    await dio.post<dynamic>(
      '/api/v1/auth/password/forgot',
      data: {'email': 'e'},
    );

    for (final request in adapterOf(dio).seen) {
      expect((request.data as Map).containsKey('device'), isFalse);
    }
  });

  test('does not change a body that is not JSON (an upload)', () async {
    final dio = dioWith((_) => jsonBody({'ok': true}, 200));
    final form = FormData.fromMap({'file': 'x'});

    await dio.post<dynamic>('/api/v1/auth/login', data: form);

    expect(adapterOf(dio).seen.single.data, same(form));
  });

  for (final code in ['DEVICE_PENDING', 'DEVICE_BLOCKED', 'DEVICE_REMOVED']) {
    test('reports a $code refusal once and still fails the call', () async {
      final dio = dioWith((_) => jsonBody({'error_code': code}, 403));

      await expectLater(
        dio.get<dynamic>('/api/v1/orders'),
        throwsA(isA<DioException>()),
      );

      expect(refusals, [code]);
    });
  }

  test('ignores other failures, including a plain 403', () async {
    final dio = dioWith(
      (_) => jsonBody({'error_code': 'PERMISSION_DENIED'}, 403),
    );

    await expectLater(
      dio.get<dynamic>('/api/v1/orders'),
      throwsA(isA<DioException>()),
    );

    expect(refusals, isEmpty);
  });

  test('deviceErrorCode finds only device codes', () {
    DioException failing(Object? data) => DioException(
      requestOptions: RequestOptions(path: '/x'),
      response: Response(
        requestOptions: RequestOptions(path: '/x'),
        statusCode: 403,
        data: data,
      ),
    );

    expect(
      deviceErrorCode(failing({'error_code': 'DEVICE_BLOCKED'})),
      'DEVICE_BLOCKED',
    );
    expect(deviceErrorCode(failing({'error_code': 'NOPE'})), isNull);
    expect(deviceErrorCode(failing('text')), isNull);
    expect(deviceErrorCode(failing(null)), isNull);
  });
}
