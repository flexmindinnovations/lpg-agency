/// Authentication for both mobile apps — session storage, the backend's
/// `/auth/*` API (via `api_client`), and reactive session state
/// (Phase 6, `docs/architecture/06-authentication-authorization.md`).
///
/// OTP login is the primary flow here (Customer/Driver apps); password
/// login is the Dashboard's flow (`frontend/libs/auth/feature-login`) — both
/// authenticate against the same backend Identity module.
library;

export 'src/token_storage.dart';
export 'src/auth_repository.dart';
export 'src/auth_state.dart';
