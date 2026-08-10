/// Hand-written HTTP client for the backend's `/auth/*` endpoints (ADR-037).
///
/// A generated client isn't justified for ~8 routes yet — this package is
/// the explicit revisit trigger: once a business-domain phase (customer,
/// order, delivery) adds a comparably wide endpoint surface, re-evaluate
/// generator tooling the way `frontend`'s `ng-openapi-gen` already does for
/// the Dashboard.
library;

export 'src/api_client.dart';
export 'src/auth_api.dart';
export 'src/models.dart';
