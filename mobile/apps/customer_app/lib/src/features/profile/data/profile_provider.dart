import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

/// Provides the current customer's profile data.
final profileProvider = FutureProvider<CustomerResponse?>((ref) async {
  final api = ref.watch(customerApiProvider);
  final authController = ref.watch(authControllerProvider);

  if (authController.state.status == AuthStatus.authenticated &&
      authController.state.principal != null) {
    final result = await api.getMyProfile();
    return result.when(
      onSuccess: (data) => data,
      onFailure: (failure) => throw Exception(failure.message),
    );
  }

  return null;
});
