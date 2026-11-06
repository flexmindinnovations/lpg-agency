import 'result.dart';

/// An exception that wraps the [Failure] behind it, so `quietRetry` can tell a
/// transient failure from a permanent one without knowing each app's own
/// exception type.
abstract interface class FailureCarrier implements Exception {
  Failure get failure;
}

/// What a provider throws for a failed call: keeps the [failure] (and its
/// error code) so `quietRetry` can decide, and prints as the failure's
/// message, as the `Exception(failure.message)` it replaces did.
class FailureException implements FailureCarrier {
  const FailureException(this.failure);

  @override
  final Failure failure;

  @override
  String toString() => failure.message;
}
