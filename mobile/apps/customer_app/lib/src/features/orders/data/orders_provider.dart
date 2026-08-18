import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

/// Provides the current customer's list of orders.
final ordersProvider = FutureProvider<List<OrderResponse>>((ref) async {
  print('ordersProvider evaluated. Auth status: ${ref.watch(authControllerProvider).state.status}');
  final api = ref.watch(orderApiProvider);
  final authController = ref.watch(authControllerProvider);
  
  if (authController.state.status == AuthStatus.authenticated && authController.state.principal != null) {
    print('ordersProvider: fetching orders');
    try {
      final result = await api.getMyOrders();
      print('ordersProvider: result received: ${result.runtimeType}');
      return result.when(
        onSuccess: (data) {
          print('ordersProvider: success, got ${data.items.length} items');
          return data.items;
        },
        onFailure: (failure) {
          print('ordersProvider: failure: ${failure.message}');
          throw Exception(failure.message);
        },
      );
    } catch (e) {
      print('ordersProvider: exception $e');
      throw Exception(e.toString());
    }
  }
  
  print('ordersProvider: Returning empty list');
  return [];
});
