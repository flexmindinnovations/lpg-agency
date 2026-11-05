/// Shared primitives used by both mobile applications.
///
/// Deliberately framework-light: no Flutter widgets, no HTTP client. Those
/// belong in `design_system` and `api_client` respectively.
library;

export 'src/error_kind.dart';
export 'src/failure_carrier.dart';
export 'src/phone_number.dart';
export 'src/push_routing.dart';
export 'src/result.dart';
