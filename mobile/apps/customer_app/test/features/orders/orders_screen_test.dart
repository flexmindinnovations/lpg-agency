import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/orders_provider.dart';
import 'package:customer_app/src/features/orders/presentation/orders_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

OrderResponse _order({
  String id = 'abcdef01aaaabbbb',
  String status = 'confirmed',
  double? totalAmount = 1234.5,
}) => OrderResponse(
  id: id,
  orderNumber: 'ORD000042',
  tenantId: 't1',
  branchId: 'b1',
  customerId: 'c1',
  addressId: 'a1',
  deliveryAddress: const DeliveryAddressPayload(addressLine: '12 Baker Street'),
  status: status,
  bookingSource: 'mobile_app',
  requestedDate: DateTime(2026, 8, 20, 10, 30),
  metadata: const {},
  totalAmount: totalAmount,
  lines: const [],
);

Widget _screen({List<OrderResponse>? orders, Object? error}) => ProviderScope(
  overrides: [
    ordersProvider.overrideWith((ref) async {
      if (error != null) throw error;
      return orders ?? const [];
    }),
  ],
  child: MaterialApp(theme: LpgTheme.light, home: const OrdersScreen()),
);

void main() {
  group('OrdersScreen', () {
    testWidgets('shows the empty state with a "Book Cylinder" action', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(orders: const []));

      expect(find.text('No orders yet'), findsOneWidget);
      expect(find.text('Book Cylinder'), findsOneWidget);
    });

    testWidgets('renders an order card with its number, status and amount', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(orders: [_order()]));

      expect(find.textContaining('ABCDEF01'), findsOneWidget);
      expect(find.text('CONFIRMED'), findsOneWidget);
      expect(find.textContaining('1234.50'), findsOneWidget);
    });

    testWidgets('an out-for-delivery order offers a Track action', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(orders: [_order(status: 'out_for_delivery')]));

      expect(find.text('Track'), findsOneWidget);
    });

    testWidgets('shows a pending amount when the order has no total yet', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(orders: [_order(totalAmount: null)]));

      expect(find.text('Pending'), findsOneWidget);
    });

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('network down')));

      expect(find.textContaining('Failed to load orders'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
