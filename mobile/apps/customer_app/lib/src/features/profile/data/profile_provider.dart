import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

/// Provides the current customer's profile data.
final profileProvider = FutureProvider<CustomerResponse?>((ref) async {
  print('profileProvider evaluated. Auth status: ${ref.watch(authControllerProvider).state.status}');
  final api = ref.watch(customerApiProvider);
  final authController = ref.watch(authControllerProvider);
  
  if (authController.state.status == AuthStatus.authenticated && authController.state.principal != null) {
    final customerId = authController.state.principal!.userId;
    try {
      final result = await api.getCustomer(customerId);
      print('profileProvider: result received: ${result.runtimeType}');
      return result.when(
        onSuccess: (data) {
          print('profileProvider: success!');
          return data;
        },
        onFailure: (failure) {
          print('profileProvider: failure: ${failure.message}');
          throw Exception(failure.message);
        },
      );
    } catch (e) {
      print('profileProvider: Exception thrown: $e');
      return null;
    }
  }
  
  print('profileProvider: Returning null');
  return null;
});
