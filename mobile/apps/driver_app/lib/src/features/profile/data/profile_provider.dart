import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_provider.dart';
import '../../../auth_provider.dart';

/// The calling driver's own profile (`GET /drivers/me`) — name, phone,
/// licence, status and current vehicle for the Profile tab.
final driverProfileProvider = FutureProvider<DriverMe>((ref) async {
  final authController = ref.watch(authControllerProvider);
  if (authController.state.status != AuthStatus.authenticated) {
    throw Exception('Not signed in.');
  }

  final result = await ref.watch(driverApiProvider).getMe();
  return result.when(
    onSuccess: (profile) => profile,
    onFailure: (failure) => throw Exception(failure.message),
  );
});
