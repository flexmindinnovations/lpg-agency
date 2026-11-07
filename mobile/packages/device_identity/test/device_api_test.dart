import 'package:device_identity/device_identity.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

void main() {
  test('reads an approved phone', () async {
    final api = DeviceApi(
      fakeDio(
        (_) => jsonBody({
          'control': 'enforce',
          'status': 'approved',
          'display_name': 'Van 2',
          'allowed': true,
        }, 200),
      ),
    );

    final report = (await api.me()).when(
      onSuccess: (r) => r,
      onFailure: (f) => fail('unexpected $f'),
    );

    expect(report.status, 'approved');
    expect(report.allowed, isTrue);
    expect(report.displayName, 'Van 2');
    expect(report.control, 'enforce');
  });

  test('reads a waiting phone', () async {
    final api = DeviceApi(
      fakeDio(
        (_) => jsonBody({
          'control': 'enforce',
          'status': 'pending',
          'display_name': null,
          'allowed': false,
        }, 200),
      ),
    );

    final report = (await api.me()).when(
      onSuccess: (r) => r,
      onFailure: (f) => fail('unexpected $f'),
    );

    expect(report.status, 'pending');
    expect(report.allowed, isFalse);
  });

  test('carries the server error code on a refusal', () async {
    final api = DeviceApi(
      fakeDio(
        (_) =>
            jsonBody({'error_code': 'DEVICE_REQUIRED', 'detail': 'No.'}, 401),
      ),
    );

    final failure = (await api.me()).when(
      onSuccess: (_) => fail('should fail'),
      onFailure: (f) => f,
    );

    expect(failure.errorCode, 'DEVICE_REQUIRED');
  });

  test('a network failure has no code, so it changes nothing', () async {
    final api = DeviceApi(
      fakeDio(
        (options) => throw DioException.connectionError(
          requestOptions: options,
          reason: 'offline',
        ),
      ),
    );

    final failure = (await api.me()).when(
      onSuccess: (_) => fail('should fail'),
      onFailure: (f) => f,
    );

    expect(failure.errorCode, isNull);
  });

  test('reads whether the phone still needs a name', () async {
    final api = DeviceApi(
      fakeDio(
        (_) => jsonBody({
          'control': 'enforce',
          'status': 'pending',
          'display_name': 'device_a1b2c3d4',
          'allowed': false,
          'needs_name': true,
        }, 200),
      ),
    );

    final report = (await api.me()).when(
      onSuccess: (r) => r,
      onFailure: (f) => fail('unexpected $f'),
    );

    expect(report.needsName, isTrue);
    expect(report.displayName, 'device_a1b2c3d4');
  });

  test('a phone the agency already knows does not need a name', () async {
    final api = DeviceApi(
      fakeDio(
        (_) => jsonBody({
          'control': 'enforce',
          'status': 'approved',
          'display_name': 'Van 2',
          'allowed': true,
        }, 200),
      ),
    );

    final report = (await api.me()).when(
      onSuccess: (r) => r,
      onFailure: (f) => fail('unexpected $f'),
    );

    expect(report.needsName, isFalse);
  });

  test('sets the name with PUT /devices/me/name', () async {
    final adapterBodies = <RequestOptions>[];
    final api = DeviceApi(
      fakeDio((options) {
        adapterBodies.add(options);
        return jsonBody({
          'control': 'enforce',
          'status': 'approved',
          'display_name': 'Van 2',
          'allowed': true,
          'needs_name': false,
        }, 200);
      }),
    );

    final report = (await api.setName('Van 2'))
        .when(onSuccess: (r) => r, onFailure: (f) => fail('unexpected $f'));

    expect(adapterBodies.single.method, 'PUT');
    expect(adapterBodies.single.path, '/api/v1/devices/me/name');
    expect(adapterBodies.single.data, {'name': 'Van 2'});
    expect(report.displayName, 'Van 2');
    expect(report.needsName, isFalse);
  });

  test('a taken name comes back with the server message and code', () async {
    final api = DeviceApi(
      fakeDio(
        (_) => jsonBody({
          'error_code': 'DUPLICATE_DEVICE_NAME',
          'detail':
              "Another phone already has the name 'Van 2'. Try 'Van 2 2'.",
        }, 409),
      ),
    );

    final failure = (await api.setName('Van 2'))
        .when(onSuccess: (r) => fail('unexpected $r'), onFailure: (f) => f);

    expect(failure.errorCode, 'DUPLICATE_DEVICE_NAME');
    expect(failure.message, contains('Van 2 2'));
  });
}
