import 'dart:convert';
import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
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

AuthApi _authApiReturning(
  Map<String, ResponseBody Function(RequestOptions)> byPath,
) {
  final client = ApiClient(baseUrl: 'https://api.test');
  client.dio.httpClientAdapter = _FakeHttpClientAdapter((options) {
    final handler = byPath.entries
        .firstWhere((entry) => options.path.contains(entry.key))
        .value;
    return handler(options);
  });
  return AuthApi(client.dio);
}

SecureTokenStorage _inMemoryTokenStorage([Map<String, String>? seed]) {
  final store = seed ?? <String, String>{};
  return SecureTokenStorage(
    write: (key, value) async => store[key] = value,
    read: (key) async => store[key],
    delete: (key) async => store.remove(key),
  );
}

void main() {
  group('ApiAuthRepository', () {
    test(
      'login persists both tokens and returns the hydrated principal',
      () async {
        final authApi = _authApiReturning({
          '/auth/login': (_) => _jsonResponse({
            'access_token': 'access-1',
            'refresh_token': 'refresh-1',
          }, 200),
          '/auth/me': (_) => _jsonResponse({
            'user_id': 'user-1',
            'tenant_id': 'tenant-1',
            'role': 'driver',
            'permissions': ['orders:deliver'],
          }, 200),
        });
        final tokenStorage = _inMemoryTokenStorage();
        final repository = ApiAuthRepository(
          authApi: authApi,
          tokenStorage: tokenStorage,
        );

        final result = await repository.login(
          email: 'driver@example.com',
          password: 'correct-horse',
        );

        final principal = result.when(
          onSuccess: (p) => p,
          onFailure: (_) => null,
        );
        expect(principal?.role, 'driver');
        expect(repository.accessToken, 'access-1');
        expect(await tokenStorage.readRefreshToken(), 'refresh-1');
      },
    );

    test('login surfaces the failure without touching stored tokens', () async {
      final authApi = _authApiReturning({
        '/auth/login': (_) =>
            _jsonResponse({'error_code': 'INVALID_CREDENTIALS'}, 401),
      });
      final tokenStorage = _inMemoryTokenStorage();
      final repository = ApiAuthRepository(
        authApi: authApi,
        tokenStorage: tokenStorage,
      );

      final result = await repository.login(
        email: 'driver@example.com',
        password: 'wrong',
      );

      final failure = result.when(onSuccess: (_) => null, onFailure: (f) => f);
      expect(failure?.errorCode, 'INVALID_CREDENTIALS');
      expect(repository.accessToken, isNull);
      expect(await tokenStorage.readRefreshToken(), isNull);
    });

    test(
      'restoreSession fails fast with NO_SESSION when nothing is stored',
      () async {
        final authApi = _authApiReturning({});
        final repository = ApiAuthRepository(
          authApi: authApi,
          tokenStorage: _inMemoryTokenStorage(),
        );

        final result = await repository.restoreSession();

        final failure = result.when(
          onSuccess: (_) => null,
          onFailure: (f) => f,
        );
        expect(failure?.errorCode, 'NO_SESSION');
      },
    );

    test('restoreSession redeems a stored refresh token', () async {
      final authApi = _authApiReturning({
        '/auth/refresh': (_) => _jsonResponse({
          'access_token': 'access-2',
          'refresh_token': 'refresh-2',
        }, 200),
        '/auth/me': (_) => _jsonResponse({
          'user_id': 'user-1',
          'tenant_id': 'tenant-1',
          'role': 'driver',
          'permissions': <String>[],
        }, 200),
      });
      final tokenStorage = _inMemoryTokenStorage({
        'auth.refresh_token': 'refresh-1',
      });
      final repository = ApiAuthRepository(
        authApi: authApi,
        tokenStorage: tokenStorage,
      );

      final result = await repository.restoreSession();

      expect(
        result.when(onSuccess: (p) => p.userId, onFailure: (_) => null),
        'user-1',
      );
      expect(repository.accessToken, 'access-2');
    });

    test('logout clears both the in-memory token and stored tokens', () async {
      final authApi = _authApiReturning({
        '/auth/logout': (_) => _jsonResponse({}, 204),
      });
      final tokenStorage = _inMemoryTokenStorage({
        'auth.access_token': 'access-1',
        'auth.refresh_token': 'refresh-1',
      });
      final repository = ApiAuthRepository(
        authApi: authApi,
        tokenStorage: tokenStorage,
      );

      await repository.logout();

      expect(repository.accessToken, isNull);
      expect(await tokenStorage.readAccessToken(), isNull);
      expect(await tokenStorage.readRefreshToken(), isNull);
    });

    test(
      'logout is a no-op against the API when no refresh token was ever stored',
      () async {
        var logoutCalled = false;
        final authApi = _authApiReturning({
          '/auth/logout': (_) {
            logoutCalled = true;
            return _jsonResponse({}, 204);
          },
        });
        final repository = ApiAuthRepository(
          authApi: authApi,
          tokenStorage: _inMemoryTokenStorage(),
        );

        await repository.logout();

        expect(logoutCalled, isFalse);
      },
    );
  });
}
