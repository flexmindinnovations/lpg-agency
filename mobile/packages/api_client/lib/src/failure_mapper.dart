import 'package:core/core.dart';
import 'package:dio/dio.dart';

/// Converts any [DioException] into the same [Failure] shape every caller
/// across both apps gets, so a screen never has to branch on Dio's own
/// exception types — only on [Failure.errorCode] (ADR-021), matching the
/// Dashboard's `toAppError` (`frontend/libs/shared/data-access/src/lib
/// /problem-details.ts`).
Failure mapDioError(DioException error) {
  switch (error.type) {
    case DioExceptionType.connectionError:
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.sendTimeout:
      return const Failure(
        message:
            'Cannot reach the server. Check your connection and try again.',
        errorCode: 'NETWORK_UNAVAILABLE',
      );
    default:
      break;
  }

  final data = error.response?.data;
  if (data is Map<String, dynamic> && data['error_code'] is String) {
    final detail = data['detail'];
    final title = data['title'];
    return Failure(
      message: (detail is String && detail.isNotEmpty)
          ? detail
          : (title is String && title.isNotEmpty)
          ? title
          : 'Something went wrong. Please try again.',
      errorCode: data['error_code'] as String,
    );
  }

  return Failure(
    message: error.message ?? 'Something went wrong. Please try again.',
    errorCode: 'UNEXPECTED_RESPONSE',
  );
}
