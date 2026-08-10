import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The Customer App's session controller.
///
/// `main()` wires the real `ApiClient`/`AuthApi`/`ApiAuthRepository` chain
/// and overrides this provider with the constructed `AuthController` before
/// the first frame — mirrors the Driver App's `auth_provider.dart`, itself
/// mirroring `local_database_provider.dart`'s pattern from Phase 5. The
/// default here exists only to fail loudly if that override is ever missed.
final authControllerProvider = Provider<AuthController>(
  (ref) => throw UnimplementedError(
    'authControllerProvider must be overridden in main() with a wired AuthController.',
  ),
);
