import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// Invoices per page of the list.
const invoicePageSize = 50;

/// What the invoice list asks the server for.
class InvoiceQuery {
  const InvoiceQuery({this.search = '', this.status, this.customerId});

  final String search;
  final String? status;
  final String? customerId;

  @override
  bool operator ==(Object other) =>
      other is InvoiceQuery &&
      other.search == search &&
      other.status == status &&
      other.customerId == customerId;

  @override
  int get hashCode => Object.hash(search, status, customerId);
}

/// One page (1-indexed) of invoices matching [InvoiceQuery].
final invoicesProvider =
    FutureProvider.family<InvoicePageResponse, (InvoiceQuery, int)>((
      ref,
      key,
    ) async {
      final query = key.$1;
      return unwrap(
        await ref
            .watch(invoiceApiProvider)
            .getMyInvoices(
              page: key.$2,
              pageSize: invoicePageSize,
              search: query.search.isEmpty ? null : query.search,
              status: query.status,
              customerId: query.customerId,
            ),
      );
    });

final invoiceDetailProvider = FutureProvider.family<InvoiceResponse, String>((
  ref,
  invoiceId,
) async {
  return unwrap(await ref.watch(invoiceApiProvider).getInvoice(invoiceId));
});

/// The UPI QR for what is still owed on an invoice. Fails with a 409 when the
/// agency has no UPI ID set up, which the screen explains.
final invoiceUpiQrProvider = FutureProvider.autoDispose.family<UpiQr, String>((
  ref,
  invoiceId,
) async {
  return unwrap(
    await ref.watch(paymentApiProvider).getUpiQr(invoiceId: invoiceId),
  );
});
