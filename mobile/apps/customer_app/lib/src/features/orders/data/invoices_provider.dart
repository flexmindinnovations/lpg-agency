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
///
/// `autoDispose` so every visit refetches it and shows the balance as it is
/// now, not as it was when the invoice was first opened.
final invoiceDetailProvider = FutureProvider.autoDispose
    .family<InvoiceResponse?, String>((ref, id) async {
      final api = ref.watch(invoiceApiProvider);
      final result = await api.getInvoice(id);
      return result.when(
        onSuccess: (data) => data,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });
