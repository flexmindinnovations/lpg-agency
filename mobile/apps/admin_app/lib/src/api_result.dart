import 'package:core/core.dart';

/// A failed API call surfaced through a provider's `AsyncError`, carrying the
/// user-facing [message] so screens never show a raw `Exception: ...`.
class ApiException implements Exception {
  const ApiException(this.failure);

  final Failure failure;

  String get message => switch (failure.errorCode) {
    'FORBIDDEN' ||
    'PERMISSION_DENIED' => 'You do not have permission to view this.',
    _ => failure.message,
  };

  @override
  String toString() => message;
}

/// Unwraps a [Result], throwing an [ApiException] on failure.
T unwrap<T>(Result<T> result) => switch (result) {
  Success(:final value) => value,
  FailureResult(:final failure) => throw ApiException(failure),
};

/// A short message for any error a provider can hold.
String errorMessage(Object error) => error is ApiException
    ? error.message
    : 'Something went wrong. Please try again.';
