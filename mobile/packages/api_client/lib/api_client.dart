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
export 'src/complaint_api.dart';
export 'src/customer_api.dart';
export 'src/cylinder_ledger_api.dart';
export 'src/cylinder_type_api.dart';
export 'src/invoice_api.dart';
export 'src/kyc_api.dart';
export 'src/notification_api.dart';
export 'src/order_api.dart';
export 'src/route_api.dart';
export 'src/models/models.dart';
