import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// How many hits of each kind the search screen previews; "See all" opens
/// the full, filtered list.
const searchPreviewSize = 5;

/// Orders, customers and invoices matching one search text.
class SearchResults {
  const SearchResults({
    required this.orders,
    required this.orderTotal,
    required this.customers,
    required this.customerTotal,
    required this.invoices,
    required this.invoiceTotal,
  });

  final List<OrderResponse> orders;
  final int orderTotal;
  final List<CustomerResponse> customers;
  final int customerTotal;
  final List<InvoiceResponse> invoices;
  final int invoiceTotal;

  bool get isEmpty => orders.isEmpty && customers.isEmpty && invoices.isEmpty;
}

/// One search across the three things an owner looks for by name or number.
/// A kind the signed-in staff member cannot read just comes back empty
/// rather than failing the whole search.
final searchResultsProvider = FutureProvider.family<SearchResults, String>((
  ref,
  query,
) async {
  final text = query.trim();
  final orderApi = ref.watch(orderApiProvider);
  final customerApi = ref.watch(customerApiProvider);
  final invoiceApi = ref.watch(invoiceApiProvider);

  final results = await (
    orderApi.getMyOrders(search: text, size: searchPreviewSize),
    customerApi.listCustomers(search: text, limit: searchPreviewSize),
    invoiceApi.getMyInvoices(search: text, pageSize: searchPreviewSize),
  ).wait;

  final orders = switch (results.$1) {
    Success<OrderPageResponse>(:final value) => value,
    _ => null,
  };
  final customers = switch (results.$2) {
    Success<CustomerPageResponse>(:final value) => value,
    _ => null,
  };
  final invoices = switch (results.$3) {
    Success<InvoicePageResponse>(:final value) => value,
    _ => null,
  };

  // Every kind failing means the problem is the connection, not the query.
  if (orders == null && customers == null && invoices == null) {
    unwrap(results.$1);
  }

  return SearchResults(
    orders: orders?.items ?? const [],
    orderTotal: orders?.total ?? 0,
    customers: customers?.items ?? const [],
    customerTotal: customers?.total ?? 0,
    invoices: invoices?.items ?? const [],
    invoiceTotal: invoices?.total ?? 0,
  );
});
