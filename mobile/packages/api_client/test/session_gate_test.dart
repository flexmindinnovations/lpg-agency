import 'dart:async';
import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Records the Authorization header of each request and answers 200.
class _Recorder implements HttpClientAdapter {
  final List<String?> sentTokens = [];
  final List<String> paths = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    paths.add(options.path);
    sentTokens.add(options.headers['Authorization'] as String?);
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

void main() {
  test('a request made before the session is ready waits, then carries the '
      'token', () async {
    final ready = Completer<void>();
    String? token; // null until the restore finishes
    final recorder = _Recorder();
    final client = ApiClient(
      baseUrl: 'https://api.test',
      getAccessToken: () => token,
      waitForSession: () => ready.future,
    )..dio.httpClientAdapter = recorder;

    final response = client.dio.get<void>('/api/v1/dashboard/summary');
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(recorder.paths, isEmpty, reason: 'held back while restoring');

    token = 'fresh-token';
    ready.complete();
    await response;

    expect(recorder.sentTokens, ['Bearer fresh-token']);
  });

  test(
    'the auth endpoints never wait, or the restore would wait for itself',
    () async {
      final never = Completer<void>(); // the session never becomes ready
      final recorder = _Recorder();
      final client = ApiClient(
        baseUrl: 'https://api.test',
        waitForSession: () => never.future,
      )..dio.httpClientAdapter = recorder;

      await client.dio.post<void>('/api/v1/auth/refresh');
      await client.dio.get<void>('/api/v1/auth/me');
      await client.dio.post<void>('/api/v1/auth/login');

      expect(recorder.paths, [
        '/api/v1/auth/refresh',
        '/api/v1/auth/me',
        '/api/v1/auth/login',
      ]);
    },
  );

  test('without a gate nothing changes', () async {
    final recorder = _Recorder();
    final client = ApiClient(
      baseUrl: 'https://api.test',
      getAccessToken: () => 't',
    )..dio.httpClientAdapter = recorder;

    await client.dio.get<void>('/api/v1/orders');

    expect(recorder.sentTokens, ['Bearer t']);
  });
}
