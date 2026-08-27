import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// Shared test double for [Dio]'s HTTP layer — every `*_api_test.dart` file
/// stubs a response without making a real request.
class FakeHttpClientAdapter implements HttpClientAdapter {
  FakeHttpClientAdapter(this.handler);

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

ResponseBody jsonResponse(Object body, int statusCode) =>
    ResponseBody.fromString(
      jsonEncode(body),
      statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

ResponseBody emptyResponse(int statusCode) =>
    ResponseBody.fromString('', statusCode);
