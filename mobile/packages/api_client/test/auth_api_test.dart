import 'dart:convert';
import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeHttpClientAdapter implements HttpClientAdapter {
  _FakeHttpClientAdapter(this.handler);

  final ResponseBody Function(RequestOptions options) handler;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async => handler(options);

  @override
  void close({bool force = false}) {}
}

ResponseBody _jsonResponse(Object body, int statusCode) =>
    ResponseBody.fromString(
      jsonEncode(body),
      statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

void main() {
  group('AuthApi', () {
    test('login maps a 200 into a Success(TokenPair)', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = _FakeHttpClientAdapter(
        (options) => _jsonResponse({
          'access_token': 'the-access-token',
          'refresh_token': 'the-refresh-token',
        }, 200),
      );
      final authApi = AuthApi(client.dio);

      final result = await authApi.login(
        email: 'staff@example.com',
        password: 'correct-horse',
      );

      expect(
        result.when(
          onSuccess: (pair) => (pair.accessToken, pair.refreshToken),
          onFailure: (_) => null,
        ),
        ('the-access-token', 'the-refresh-token'),
      );
    });

    test(
      'login maps a 401 Problem Details body into a Failure with the error_code',
      () async {
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = _FakeHttpClientAdapter(
          (options) => _jsonResponse({
            'error_code': 'INVALID_CREDENTIALS',
            'title': 'Invalid credentials',
            'detail': 'Incorrect email or password.',
          }, 401),
        );
        final authApi = AuthApi(client.dio);

        final result = await authApi.login(
          email: 'staff@example.com',
          password: 'wrong',
        );

        final failure = result.when(
          onSuccess: (_) => null,
          onFailure: (failure) => failure,
        );
        expect(failure, isA<Failure>());
        expect(failure!.errorCode, 'INVALID_CREDENTIALS');
        expect(failure.message, 'Incorrect email or password.');
      },
    );

    test('me maps a 200 into a Success(Principal)', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = _FakeHttpClientAdapter(
        (options) => _jsonResponse({
          'user_id': 'user-1',
          'tenant_id': 'tenant-1',
          'role': 'driver',
          'permissions': ['orders:deliver'],
        }, 200),
      );
      final authApi = AuthApi(client.dio);

      final result = await authApi.me();

      final principal = result.when(
        onSuccess: (p) => p,
        onFailure: (_) => null,
      );
      expect(principal, isNotNull);
      expect(principal!.role, 'driver');
      expect(principal.permissions, {'orders:deliver'});
    });

    test('a network failure maps to NETWORK_UNAVAILABLE', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = _FakeHttpClientAdapter((options) {
        throw DioException.connectionError(
          requestOptions: options,
          reason: 'connection refused',
        );
      });
      final authApi = AuthApi(client.dio);

      final result = await authApi.me();

      final failure = result.when(
        onSuccess: (_) => null,
        onFailure: (failure) => failure,
      );
      expect(failure!.errorCode, 'NETWORK_UNAVAILABLE');
    });
  });
}
