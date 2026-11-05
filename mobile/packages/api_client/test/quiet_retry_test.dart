import 'package:api_client/api_client.dart';
import 'package:api_client/src/failure_mapper.dart';
import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

class _Wrapped implements FailureCarrier {
  const _Wrapped(this.failure);

  @override
  final Failure failure;
}

DioException _dio(DioExceptionType type, {int? status, Object? body}) =>
    DioException(
      requestOptions: RequestOptions(path: '/x'),
      type: type,
      response: status == null
          ? null
          : Response<Object?>(
              requestOptions: RequestOptions(path: '/x'),
              statusCode: status,
              data: body,
            ),
    );

void main() {
  group('quietRetry', () {
    test('retries a network failure once, after a short pause', () {
      const error = Failure(
        message: 'offline',
        errorCode: 'NETWORK_UNAVAILABLE',
      );

      expect(quietRetry(0, error), quietRetryDelay);
      expect(quietRetry(1, error), isNull);
    });

    test('retries a failure wrapped by an app exception', () {
      const error = _Wrapped(
        Failure(message: 'busy', errorCode: 'SERVER_UNAVAILABLE'),
      );

      expect(quietRetry(0, error), quietRetryDelay);
    });

    test('retries a raw dio timeout and a bad gateway', () {
      expect(
        quietRetry(0, _dio(DioExceptionType.receiveTimeout)),
        quietRetryDelay,
      );
      expect(
        quietRetry(0, _dio(DioExceptionType.badResponse, status: 502)),
        quietRetryDelay,
      );
    });

    test('does not retry an answer the server gave on purpose', () {
      for (final code in ['FORBIDDEN', 'NOT_FOUND', 'VALIDATION_ERROR']) {
        expect(quietRetry(0, Failure(message: 'no', errorCode: code)), isNull);
      }
      expect(
        quietRetry(
          0,
          _dio(
            DioExceptionType.badResponse,
            status: 403,
            body: {'error_code': 'FORBIDDEN'},
          ),
        ),
        isNull,
      );
    });

    test('does not retry a programming error', () {
      expect(quietRetry(0, StateError('bug')), isNull);
      expect(quietRetry(0, const FormatException('bad json')), isNull);
    });
  });

  group('mapDioError', () {
    test('names a 503 from the gateway, whatever its body says', () {
      final failure = mapDioError(
        _dio(DioExceptionType.badResponse, status: 503, body: '<html>'),
      );

      expect(failure.errorCode, 'SERVER_UNAVAILABLE');
    });

    test('still returns the server error code on other statuses', () {
      final failure = mapDioError(
        _dio(
          DioExceptionType.badResponse,
          status: 409,
          body: {'error_code': 'ORDER_LOCKED', 'detail': 'Locked.'},
        ),
      );

      expect(failure.errorCode, 'ORDER_LOCKED');
    });
  });
}
