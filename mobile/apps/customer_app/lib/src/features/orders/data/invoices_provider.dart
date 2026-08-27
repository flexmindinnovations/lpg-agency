import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

/// Provides the current customer's invoices.
final invoicesProvider = FutureProvider<List<InvoiceResponse>>((ref) async {
  final api = ref.watch(invoiceApiProvider);
  final authController = ref.watch(authControllerProvider);

  if (authController.state.status == AuthStatus.authenticated &&
      authController.state.principal != null) {
    final result = await api.getMyInvoices();
    return result.when(
      onSuccess: (data) => data.items,
      onFailure: (failure) => throw Exception(failure.message),
    );
  }

  return [];
});

/// Provides a single invoice by its ID.
final invoiceDetailProvider = FutureProvider.family<InvoiceResponse?, String>((
  ref,
  id,
) async {
  final api = ref.watch(invoiceApiProvider);
  final result = await api.getInvoice(id);
  return result.when(
    onSuccess: (data) => data,
    onFailure: (failure) => throw Exception(failure.message),
  );
});
