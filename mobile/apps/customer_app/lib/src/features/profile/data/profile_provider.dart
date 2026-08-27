import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

/// Provides the current customer's profile data.
final profileProvider = FutureProvider<CustomerResponse?>((ref) async {
  final api = ref.watch(customerApiProvider);
  final authController = ref.watch(authControllerProvider);

  debugPrint(
    'profileProvider: status=${authController.state.status}, principal=${authController.state.principal?.userId}',
  );

  if (authController.state.status == AuthStatus.authenticated &&
      authController.state.principal != null) {
    debugPrint('profileProvider: Fetching profile from /customers/me');
    final result = await api.getMyProfile();
    return result.when(
      onSuccess: (data) {
        debugPrint(
          'profileProvider: Profile loaded for ${data.fullName} (ID: ${data.id})',
        );
        return data;
      },
      onFailure: (failure) {
        debugPrint('profileProvider: API failed: ${failure.message}');
        throw Exception(failure.message);
      },
    );
  }

  debugPrint('profileProvider: Returning null (not authenticated)');
  return null;
});
