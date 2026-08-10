import 'dart:convert';
import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// A minimal fake transport — no mocking framework, matching
/// `local_storage`'s convention of injecting plain closures/fakes rather
/// than a mock object. [handler] decides the response per request; tests
/// close over a mutable counter to script multi-step behaviour (e.g.
/// "401 on the first call, 200 on the retry").
class _FakeHttpClientAdapter implements HttpClientAdapter {
  _FakeHttpClientAdapter(this.handler);

  final ResponseBody Function(RequestOptions options) handler;
  final List<RequestOptions> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return handler(options);
  }

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
  group('ApiClient', () {
    test('attaches the bearer token when one is available', () async {
      final adapter = _FakeHttpClientAdapter(
        (options) => _jsonResponse({'ok': true}, 200),
      );
      final client = ApiClient(
        baseUrl: 'https://api.test',
        getAccessToken: () => 'the-token',
      );
      client.dio.httpClientAdapter = adapter;

      await client.dio.get<void>('/api/v1/orders');

      expect(
        adapter.requests.single.headers['Authorization'],
        'Bearer the-token',
      );
    });

    test('sends no Authorization header when there is no session', () async {
      final adapter = _FakeHttpClientAdapter(
        (options) => _jsonResponse({'ok': true}, 200),
      );
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = adapter;

      await client.dio.get<void>('/api/v1/orders');

      expect(
        adapter.requests.single.headers.containsKey('Authorization'),
        isFalse,
      );
    });

    test(
      'does not attempt a refresh-and-retry for a 401 on the login endpoint itself',
      () async {
        var refreshCalls = 0;
        final adapter = _FakeHttpClientAdapter(
          (options) =>
              _jsonResponse({'error_code': 'INVALID_CREDENTIALS'}, 401),
        );
        final client = ApiClient(
          baseUrl: 'https://api.test',
          refreshAccessToken: () async {
            refreshCalls++;
            return 'new-token';
          },
        );
        client.dio.httpClientAdapter = adapter;

        await expectLater(
          client.dio.post<void>('/api/v1/auth/login', data: {}),
          throwsA(isA<DioException>()),
        );
        expect(refreshCalls, 0);
      },
    );

    test(
      'refreshes and retries once on a 401 from an ordinary endpoint',
      () async {
        var callCount = 0;
        final adapter = _FakeHttpClientAdapter((options) {
          callCount++;
          if (callCount == 1) {
            return _jsonResponse({
              'error_code': 'AUTHENTICATION_REQUIRED',
            }, 401);
          }
          expect(options.headers['Authorization'], 'Bearer refreshed-token');
          return _jsonResponse({'ok': true}, 200);
        });
        // Mirrors real wiring: `getAccessToken`/`refreshAccessToken` share the
        // same backing `TokenStorage`, so a successful refresh updates what
        // `getAccessToken` returns before the retry's own `onRequest` pass
        // re-reads it — `dio.fetch()` re-runs the whole interceptor chain,
        // it doesn't continue mid-chain the way the Dashboard's RxJS
        // interceptor does.
        var currentToken = 'stale-token';
        var sessionExpired = false;
        final client = ApiClient(
          baseUrl: 'https://api.test',
          getAccessToken: () => currentToken,
          refreshAccessToken: () async {
            currentToken = 'refreshed-token';
            return currentToken;
          },
          onSessionExpired: () => sessionExpired = true,
        );
        client.dio.httpClientAdapter = adapter;

        final response = await client.dio.get<Map<String, dynamic>>(
          '/api/v1/orders',
        );

        expect(response.data, {'ok': true});
        expect(callCount, 2);
        expect(sessionExpired, isFalse);
      },
    );

    test(
      'clears the session when the refresh itself fails to produce a token',
      () async {
        final adapter = _FakeHttpClientAdapter(
          (options) =>
              _jsonResponse({'error_code': 'AUTHENTICATION_REQUIRED'}, 401),
        );
        var sessionExpired = false;
        final client = ApiClient(
          baseUrl: 'https://api.test',
          getAccessToken: () => 'stale-token',
          refreshAccessToken: () async => null,
          onSessionExpired: () => sessionExpired = true,
        );
        client.dio.httpClientAdapter = adapter;

        await expectLater(
          client.dio.get<void>('/api/v1/orders'),
          throwsA(isA<DioException>()),
        );
        expect(sessionExpired, isTrue);
      },
    );
  });
}
