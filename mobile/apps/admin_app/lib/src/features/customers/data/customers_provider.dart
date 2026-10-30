import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// Customers per page of the list.
const customerPageSize = 50;

/// One page of customers matching a search (name, phone or consumer number);
/// `(search, page)` with the page 1-indexed.
final customersProvider =
    FutureProvider.family<CustomerPageResponse, (String, int)>((
      ref,
      key,
    ) async {
      final result = await ref
          .watch(customerApiProvider)
          .listCustomers(
            search: key.$1.isEmpty ? null : key.$1,
            skip: (key.$2 - 1) * customerPageSize,
            limit: customerPageSize,
          );
      return unwrap(result);
    });

final customerDetailProvider = FutureProvider.family<CustomerResponse, String>((
  ref,
  customerId,
) async {
  return unwrap(await ref.watch(customerApiProvider).getCustomer(customerId));
});

/// Filled cylinders the customer holds, by type. Roles without `ledger:read`
/// get an error the screen shows as a quiet note.
final customerLedgerProvider =
    FutureProvider.family<CylinderLedgerResponse, String>((
      ref,
      customerId,
    ) async {
      return unwrap(
        await ref.watch(cylinderLedgerApiProvider).getLedger(customerId),
      );
    });

/// The customer's latest orders.
final customerOrdersProvider =
    FutureProvider.family<List<OrderResponse>, String>((ref, customerId) async {
      final page = unwrap(
        await ref
            .watch(orderApiProvider)
            .getMyOrders(customerId: customerId, size: 5),
      );
      return page.items;
    });

/// The customer's invoices, newest first (one page is plenty for a summary).
final customerInvoicesProvider =
    FutureProvider.family<InvoicePageResponse, String>((ref, customerId) async {
      return unwrap(
        await ref
            .watch(invoiceApiProvider)
            .getMyInvoices(customerId: customerId, pageSize: 100),
      );
    });
