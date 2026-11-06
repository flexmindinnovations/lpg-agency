import 'package:core/core.dart';
import 'package:dio/dio.dart';

import 'failure_mapper.dart';

/// How long a screen waits before its one quiet retry. Long enough for a
/// radio that has just woken up, or a server that is still starting, to answer.
const quietRetryDelay = Duration(seconds: 2);

/// Error codes (see `mapDioError`) that mean "the server could not be reached
/// or answered badly", where asking again a moment later can succeed. A
/// structured error such as `FORBIDDEN` or `NOT_FOUND` is an answer, and
/// asking again returns the same answer.
const _transientErrorCodes = {
  'NETWORK_UNAVAILABLE',
  'SERVER_UNAVAILABLE',
  'UNEXPECTED_RESPONSE',
};

/// Whether asking again might succeed.
bool isTransientError(Object error) {
  if (error is FailureCarrier) return isTransientError(error.failure);
  if (error is Failure) return _transientErrorCodes.contains(error.errorCode);
  if (error is DioException) return isTransientError(mapDioError(error));
  return false;
}

/// The app-wide retry policy for providers (`ProviderScope(retry: ...)`).
///
/// A provider that fails for a transient reason is retried **once**, after
/// [quietRetryDelay]. Riverpod keeps the provider in its loading state while
/// it waits, so the screen keeps showing its skeleton; the error screen shows
/// only if the second attempt fails as well. Permanent failures (forbidden,
/// not found, a bug) show at once, because a retry would only delay them.
///
/// Riverpod's default retries every failure up to ten times with growing
/// delays, which hides a real error behind a skeleton for half a minute; the
/// Admin app turned retries off altogether, which showed the error screen for
/// a blip that a second attempt would have cleared.
Duration? quietRetry(int retryCount, Object error) {
  if (retryCount >= 1) return null;
  return isTransientError(error) ? quietRetryDelay : null;
}
