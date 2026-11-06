import 'failure_carrier.dart';
import 'result.dart';

/// What went wrong, in the terms a person can act on. Every error a screen can
/// hold maps to exactly one kind, and each kind has one plain-language message
/// in the design system, so the apps never show a server sentence or an
/// exception's text.
enum ErrorKind {
  /// No network, or the request never reached the server.
  offline,

  /// The server is slow, starting or asking us to slow down.
  busy,

  /// The session has ended; signing in again fixes it.
  sessionExpired,

  /// This person may not see or do this.
  forbidden,

  /// The agency's own account is not active (suspended, licence ended).
  agencyBlocked,

  /// The thing asked for does not exist (any more).
  notFound,

  /// The server understood and refused for a reason of its own (a rule, a
  /// duplicate, a value that does not fit).
  rejected,

  /// The server failed.
  server,

  /// Anything else, including an exception that is not an API error.
  unknown,
}

/// The [Failure] behind [error], or `null` when it is not an API failure.
Failure? failureOf(Object error) => switch (error) {
  FailureCarrier(:final failure) => failure,
  Failure() => error,
  _ => null,
};

/// Classifies [error] by the backend's `error_code` (ADR-021) and the client's
/// own transport codes (`NETWORK_UNAVAILABLE`, `SERVER_UNAVAILABLE`,
/// `UNEXPECTED_RESPONSE`, see `mapDioError`).
ErrorKind errorKindOf(Object error) {
  final code = failureOf(error)?.errorCode;
  if (code == null) return ErrorKind.unknown;
  return switch (code) {
    'NETWORK_UNAVAILABLE' => ErrorKind.offline,
    'SERVER_UNAVAILABLE' || 'RATE_LIMIT_EXCEEDED' => ErrorKind.busy,
    'AUTHENTICATION_REQUIRED' ||
    'REFRESH_TOKEN_INVALID' ||
    'NO_SESSION' => ErrorKind.sessionExpired,
    'PERMISSION_DENIED' || 'FORBIDDEN' => ErrorKind.forbidden,
    'TENANT_SUSPENDED' ||
    'LICENSE_EXPIRED' ||
    'LICENSE_NOT_ACTIVATED' => ErrorKind.agencyBlocked,
    'RESOURCE_NOT_FOUND' => ErrorKind.notFound,
    'INTERNAL_SERVER_ERROR' ||
    'UNKNOWN_ERROR' ||
    'HTTP_ERROR' ||
    'UNEXPECTED_RESPONSE' => ErrorKind.server,
    _ when code.endsWith('_NOT_FOUND') => ErrorKind.notFound,
    _ => ErrorKind.rejected,
  };
}

/// A short code worth showing small under the message so support can find the
/// cause: the server's own code for the kinds where the message cannot say
/// more. `null` where the message is enough (offline, busy, signed out,
/// forbidden), and for errors that are not API failures.
String? supportCodeOf(Object error) {
  final code = failureOf(error)?.errorCode;
  if (code == null) return null;
  return switch (errorKindOf(error)) {
    ErrorKind.rejected ||
    ErrorKind.server ||
    ErrorKind.agencyBlocked ||
    ErrorKind.notFound => code,
    _ => null,
  };
}
