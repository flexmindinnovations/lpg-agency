/// A success-or-failure result.
///
/// Used instead of throwing across layer boundaries, so a caller cannot
/// silently forget to handle a failure — the type system requires the switch.
/// This matters most on the Driver App's sync path, where an unhandled failure
/// would mean a delivery silently never reaching the server.
sealed class Result<T> {
  const Result();

  R when<R>({
    required R Function(T value) onSuccess,
    required R Function(Failure failure) onFailure,
  }) {
    // Callbacks are named onSuccess/onFailure rather than success/failure so
    // the destructured pattern variable below cannot shadow them — it silently
    // produced a call to the wrong thing when they shared a name.
    return switch (this) {
      Success<T>(:final value) => onSuccess(value),
      FailureResult<T>(:final failure) => onFailure(failure),
    };
  }
}

final class Success<T> extends Result<T> {
  const Success(this.value);
  final T value;
}

final class FailureResult<T> extends Result<T> {
  const FailureResult(this.failure);
  final Failure failure;
}

/// A failure carrying the backend's `error_code` where one is available,
/// so the client can branch on the same codes the API documents (ADR-021).
class Failure {
  const Failure({required this.message, this.errorCode});

  final String message;
  final String? errorCode;

  @override
  String toString() => 'Failure(${errorCode ?? 'UNKNOWN'}: $message)';
}
