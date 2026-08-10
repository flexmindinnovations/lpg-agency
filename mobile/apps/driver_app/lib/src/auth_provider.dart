import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The Driver App's session controller.
///
/// `main()` wires the real `ApiClient`/`AuthApi`/`ApiAuthRepository` chain
/// and overrides this provider with the constructed `AuthController` before
/// the first frame — exactly the `localDatabaseProvider` pattern
/// (`local_database_provider.dart`). The default here exists only to fail
/// loudly if that override is ever missed.
final authControllerProvider = Provider<AuthController>(
  (ref) => throw UnimplementedError(
    'authControllerProvider must be overridden in main() with a wired AuthController.',
  ),
);
