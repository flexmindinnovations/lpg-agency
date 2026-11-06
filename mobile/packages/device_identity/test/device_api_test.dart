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
}
