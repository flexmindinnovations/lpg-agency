import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Admin App session controller provider.
final authControllerProvider = Provider<AuthController>(
  (ref) => throw UnimplementedError(
    'authControllerProvider must be overridden in main() with a wired AuthController.',
  ),
);
